from __future__ import annotations
"""Generate LaTeX tables for the paper from experiment results.

Reads results/full_experiment.json and produces paper/tables.tex with:
- Table 1: Model comparison (accuracy, F1, AUC-ROC, latency)
- Table 2: Temporal validation results
- Table 3: Cross-validation results (5-fold)
- Table 4: Comparison with prior work (FRNN, HDL, etc.)

Usage:
    python generate_paper_tables.py --input results/full_experiment.json --output paper/tables.tex
    python generate_paper_tables.py --input results/full_experiment.json --output paper/tables.tex --lang ru
"""
import argparse
import json
import os


# ---------------------------------------------------------------------------
# Published baselines from prior work (for Table 4)
# ---------------------------------------------------------------------------
PRIOR_WORK = [
    {
        "name": "FRNN (Kates-Harbeck et al.)",
        "year": 2019,
        "ref": r"\cite{kates2019predicting}",
        "accuracy": 0.92,
        "auc_roc": 0.94,
        "notes": "DIII-D \\& JET, CNN+LSTM",
    },
    {
        "name": "HDL (Rea et al.)",
        "year": 2019,
        "ref": r"\cite{rea2019exploratory}",
        "accuracy": 0.88,
        "auc_roc": 0.92,
        "notes": "Alcator C-Mod, dense layers",
    },
    {
        "name": "De Vries et al.",
        "year": 2011,
        "ref": r"\cite{devries2011survey}",
        "accuracy": 0.85,
        "auc_roc": None,
        "notes": "JET, statistical analysis",
    },
    {
        "name": "Cannas et al.",
        "year": 2004,
        "ref": r"\cite{cannas2004disruption}",
        "accuracy": 0.88,
        "auc_roc": 0.90,
        "notes": "JET, neural networks",
    },
    {
        "name": "Rattá et al.",
        "year": 2010,
        "ref": r"\cite{ratta2010advanced}",
        "accuracy": 0.90,
        "auc_roc": 0.93,
        "notes": "ASDEX-U, SVM+manifold",
    },
]


def fmt(val: float | None, decimals: int = 4) -> str:
    """Format a float or return '---' for None."""
    if val is None:
        return "---"
    return f"{val:.{decimals}f}"


def fmt_pm(mean: float | None, std: float | None, decimals: int = 4) -> str:
    """Format mean +/- std."""
    if mean is None:
        return "---"
    if std is None:
        return fmt(mean, decimals)
    return f"${fmt(mean, decimals)} \\pm {fmt(std, decimals)}$"


# ---------------------------------------------------------------------------
# Table generators
# ---------------------------------------------------------------------------

def table_model_comparison(results: dict, lang: str = "en") -> str:
    """Table 1: Model comparison on test set."""
    if lang == "ru":
        caption = "Сравнение моделей на тестовой выборке FAIR-MAST"
        headers = ["Модель", "Accuracy", "F1", "AUC-ROC", r"P99 задержка, мс"]
    else:
        caption = "Model comparison on FAIR-MAST test set"
        headers = ["Model", "Accuracy", "F1", "AUC-ROC", "P99 Latency (ms)"]

    models = [
        ("Random Forest", "random_forest"),
        ("bi-LSTM+Attention", "lstm_attention"),
        ("Transformer", "transformer"),
    ]

    rows = []
    for display_name, key in models:
        m = results.get(key)
        if m is None:
            continue
        lat = m.get("latency", {}).get("p99_ms")
        rows.append([
            display_name,
            fmt(m.get("accuracy")),
            fmt(m.get("f1")),
            fmt(m.get("auc_roc")),
            fmt(lat, 2) if lat is not None else "---",
        ])

    return _render_table(
        label="tab:model-comparison",
        caption=caption,
        headers=headers,
        rows=rows,
        col_spec="l" + "r" * (len(headers) - 1),
    )


def table_temporal_validation(results: dict, lang: str = "en") -> str:
    """Table 2: Temporal validation results."""
    if lang == "ru":
        caption = "Результаты темпоральной валидации (обучение на ранних кампаниях, тест на поздних)"
        headers = ["Модель", "Accuracy", "F1", "AUC-ROC",
                    r"$N_{\text{train}}$", r"$N_{\text{test}}$"]
    else:
        caption = "Temporal validation results (train on early campaigns, test on later)"
        headers = ["Model", "Accuracy", "F1", "AUC-ROC",
                    r"$N_{\text{train}}$", r"$N_{\text{test}}$"]

    models = [
        ("Random Forest", "temporal_validation_rf"),
        ("bi-LSTM+Attention", "temporal_validation_lstm"),
        ("Transformer", "temporal_validation_transformer"),
    ]

    rows = []
    for display_name, key in models:
        m = results.get(key)
        if m is None or "error" in m:
            continue
        rows.append([
            display_name,
            fmt(m.get("accuracy")),
            fmt(m.get("f1")),
            fmt(m.get("auc_roc")),
            str(m.get("train_size", "---")),
            str(m.get("test_size", "---")),
        ])

    return _render_table(
        label="tab:temporal-validation",
        caption=caption,
        headers=headers,
        rows=rows,
        col_spec="l" + "r" * (len(headers) - 1),
    )


def table_cross_validation(results: dict, lang: str = "en") -> str:
    """Table 3: 5-fold cross-validation results."""
    if lang == "ru":
        caption = "Результаты 5-fold кросс-валидации"
        headers = ["Модель", "Accuracy", "F1", "AUC-ROC"]
    else:
        caption = "5-fold cross-validation results"
        headers = ["Model", "Accuracy", "F1", "AUC-ROC"]

    models = [
        ("Random Forest", "cross_validation_rf"),
        ("bi-LSTM+Attention", "cross_validation_lstm"),
        ("Transformer", "cross_validation_transformer"),
    ]

    rows = []
    for display_name, key in models:
        cv = results.get(key)
        if cv is None:
            continue
        rows.append([
            display_name,
            fmt_pm(cv.get("accuracy_mean"), cv.get("accuracy_std")),
            fmt_pm(cv.get("f1_mean"), cv.get("f1_std")),
            fmt_pm(cv.get("auc_roc_mean"), cv.get("auc_roc_std")),
        ])

    return _render_table(
        label="tab:cross-validation",
        caption=caption,
        headers=headers,
        rows=rows,
        col_spec="l" + "c" * (len(headers) - 1),
    )


def table_prior_work(results: dict, lang: str = "en") -> str:
    """Table 4: Comparison with prior work."""
    if lang == "ru":
        caption = "Сравнение с опубликованными результатами"
        headers = ["Метод", "Год", "Accuracy", "AUC-ROC", "Примечания"]
    else:
        caption = "Comparison with published results on tokamak disruption prediction"
        headers = ["Method", "Year", "Accuracy", "AUC-ROC", "Notes"]

    rows = []
    # Our models first
    our_models = [
        ("Random Forest", "random_forest"),
        ("bi-LSTM+Attention", "lstm_attention"),
        ("Transformer", "transformer"),
    ]
    for display_name, key in our_models:
        m = results.get(key)
        if m is None:
            continue
        rows.append([
            f"\\textbf{{{display_name} (ours)}}",
            "2025",
            f"\\textbf{{{fmt(m.get('accuracy'))}}}",
            f"\\textbf{{{fmt(m.get('auc_roc'))}}}",
            "MAST, this work",
        ])

    # Add separator
    rows.append(None)  # will render as \midrule

    # Published baselines
    for pw in PRIOR_WORK:
        rows.append([
            f"{pw['name']} {pw['ref']}",
            str(pw["year"]),
            fmt(pw.get("accuracy")),
            fmt(pw.get("auc_roc")),
            pw.get("notes", ""),
        ])

    return _render_table(
        label="tab:prior-work",
        caption=caption,
        headers=headers,
        rows=rows,
        col_spec="lcrrl",
        has_midrule_rows=True,
    )


# ---------------------------------------------------------------------------
# LaTeX rendering
# ---------------------------------------------------------------------------

def _render_table(label: str, caption: str, headers: list[str],
                  rows: list[list[str] | None], col_spec: str,
                  has_midrule_rows: bool = False) -> str:
    """Render a LaTeX table."""
    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        f"\\caption{{{caption}}}",
        f"\\label{{{label}}}",
        f"\\begin{{tabular}}{{{col_spec}}}",
        r"\toprule",
        " & ".join(headers) + r" \\",
        r"\midrule",
    ]

    for row in rows:
        if row is None:
            lines.append(r"\midrule")
        else:
            lines.append(" & ".join(row) + r" \\")

    lines.extend([
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
        "",
    ])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate LaTeX tables from experiment results")
    parser.add_argument("--input", default="results/full_experiment.json",
                        help="Path to experiment results JSON")
    parser.add_argument("--output", default="paper/tables.tex",
                        help="Path to output LaTeX file")
    parser.add_argument("--lang", default="en", choices=["en", "ru"],
                        help="Language for captions (en or ru)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    with open(args.input) as f:
        results = json.load(f)

    tables = []
    tables.append("% Auto-generated by generate_paper_tables.py")
    tables.append("% Do not edit manually -- re-run the script to update.")
    tables.append(r"% Requires: \usepackage{booktabs}")
    tables.append("")

    # Table 1: Model comparison
    tables.append("% " + "=" * 60)
    tables.append("% Table 1: Model comparison")
    tables.append("% " + "=" * 60)
    tables.append(table_model_comparison(results, args.lang))

    # Table 2: Temporal validation
    has_temporal = any(k.startswith("temporal_validation") for k in results)
    if has_temporal:
        tables.append("% " + "=" * 60)
        tables.append("% Table 2: Temporal validation")
        tables.append("% " + "=" * 60)
        tables.append(table_temporal_validation(results, args.lang))

    # Table 3: Cross-validation
    has_cv = any(k.startswith("cross_validation") for k in results)
    if has_cv:
        tables.append("% " + "=" * 60)
        tables.append("% Table 3: Cross-validation")
        tables.append("% " + "=" * 60)
        tables.append(table_cross_validation(results, args.lang))

    # Table 4: Comparison with prior work
    tables.append("% " + "=" * 60)
    tables.append("% Table 4: Comparison with prior work")
    tables.append("% " + "=" * 60)
    tables.append(table_prior_work(results, args.lang))

    output_text = "\n".join(tables)

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w") as f:
        f.write(output_text)

    print(f"LaTeX tables written to {args.output}")
    print(f"  Tables generated: {output_text.count(chr(92) + 'begin{table}')}")
    print(f"  Include in your paper with: \\input{{{args.output}}}")


if __name__ == "__main__":
    main()
