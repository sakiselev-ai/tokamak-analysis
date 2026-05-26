"""TokaMark Group 4 evaluation on real FAIR-MAST data (lite version for low-RAM VPS)."""
from __future__ import annotations
import json, time, gc
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

class LSTMForecaster(nn.Module):
    def __init__(self, in_s, out_s, hs=64, nl=2):
        super().__init__()
        self.lstm = nn.LSTM(in_s, hs, nl, batch_first=True, dropout=0.2)
        self.fc = nn.Linear(hs, out_s)
    def forward(self, x):
        _, (h, _) = self.lstm(x)
        return self.fc(h[-1])

def nrmse(p, t):
    r = np.sqrt(np.mean((p - t) ** 2))
    s = np.std(t)
    return float(r / s) if s > 1e-10 else 0.0

# Load real data (only 200 shots to fit in 3.8 GB RAM)
print("Loading FAIR-MAST data...")
d = np.load("data/fair_mast_500.npz")
X = d["X"][:200].copy()
del d
gc.collect()
n, T, S = X.shape
print("Data: {} shots x {} ts x {} signals".format(n, T, S))

nt = int(n * 0.7)
m = X[:nt].mean(axis=(0, 1), keepdims=True)
s = X[:nt].std(axis=(0, 1), keepdims=True)
s[s < 1e-8] = 1.0
X = (X - m) / s

PL, FL = 150, 50

tasks = {
    "4-1": {"in": list(range(14)), "out": [18, 19], "bl": 0.3445, "nm": "SXR from magnetics"},
    "4-2": {"in": list(range(12)), "out": [18, 19], "bl": 0.3311, "nm": "SXR from kinetics"},
    "4-3": {"in": list(range(14)), "out": [14, 15, 16, 17], "bl": 0.2702, "nm": "Shape params"},
    "4-4": {"in": list(range(1, 15)), "out": [0], "bl": 0.4292, "nm": "Plasma current"},
    "4-5": {"in": list(range(14)), "out": [15, 16, 17], "bl": 1.0053, "nm": "Mirnov/MHD"},
}

results = []
for tid, t in tasks.items():
    print("\n" + "=" * 50)
    print("task_{}: {}".format(tid, t["nm"]))
    print("=" * 50)
    ni, no = len(t["in"]), len(t["out"])
    Xp = X[:, :PL, :][:, :, t["in"]]
    Yf = X[:, PL:PL + FL, :][:, :, t["out"]]
    Xtr, Xte = Xp[:nt], Xp[nt:]
    Ytr, Yte = Yf[:nt], Yf[nt:]
    print("  In: ({}, {}) -> Out: ({}, {})  Train: {} Test: {}".format(
        PL, ni, FL, no, nt, n - nt))

    mdl = LSTMForecaster(ni, FL * no, hs=64, nl=2)
    opt = torch.optim.Adam(mdl.parameters(), lr=1e-3, weight_decay=1e-4)
    sch = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, patience=5, factor=0.5)
    crit = nn.MSELoss()
    ds = TensorDataset(torch.FloatTensor(Xtr), torch.FloatTensor(Ytr.reshape(nt, -1)))
    ld = DataLoader(ds, batch_size=16, shuffle=True)

    st = time.time()
    for ep in range(40):
        mdl.train()
        ls = []
        for xb, yb in ld:
            opt.zero_grad()
            p = mdl(xb)
            l = crit(p, yb)
            l.backward()
            torch.nn.utils.clip_grad_norm_(mdl.parameters(), 1.0)
            opt.step()
            ls.append(l.item())
        a = np.mean(ls)
        sch.step(a)
        if (ep + 1) % 10 == 0:
            print("  ep {}/40 mse={:.6f}".format(ep + 1, a))
    tt = time.time() - st

    mdl.eval()
    with torch.no_grad():
        pf = mdl(torch.FloatTensor(Xte)).numpy().reshape(-1, FL, no)
    nrs = [nrmse(pf[:, :, i], Yte[:, :, i]) for i in range(no)]
    avg = float(np.mean(nrs))
    b = avg < t["bl"]
    print("  NRMSE={:.4f} baseline={:.4f} {}".format(avg, t["bl"], "BEATS" if b else "below"))
    results.append({"task": "task_" + tid, "name": t["nm"], "nrmse": avg,
                    "baseline": t["bl"], "beats": b, "time_s": round(tt, 1)})
    del mdl, ds, ld, Xtr, Xte, Ytr, Yte, Xp, Yf
    gc.collect()

print("\n" + "=" * 50)
print("SUMMARY: Group 4 (Real FAIR-MAST, 200 shots)")
print("=" * 50)
print("{:<12} {:>8} {:>8} {:>8}".format("Task", "LSTM", "Base", "Result"))
print("-" * 40)
w = 0
for r in results:
    s = "BEATS" if r["beats"] else "below"
    if r["beats"]:
        w += 1
    print("{:<12} {:>8.4f} {:>8.4f} {:>8}".format(r["task"], r["nrmse"], r["baseline"], s))
al = float(np.mean([r["nrmse"] for r in results]))
print("-" * 40)
print("{:<12} {:>8.4f} {:>8.4f} {:>8}".format(
    "Average", al, 0.4761, "BEATS" if al < 0.4761 else "below"))
print("Won {}/5".format(w))

import os
os.makedirs("results", exist_ok=True)
with open("results/tokamark_group4_real.json", "w") as f:
    json.dump({"group": "4", "data": "FAIR-MAST 200 shots normalized",
               "model": "LSTM hidden=64 layers=2", "avg_nrmse": al,
               "baseline_avg": 0.4761, "tasks": results}, f, indent=2)
print("Saved results/tokamark_group4_real.json")
