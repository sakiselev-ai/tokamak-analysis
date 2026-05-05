from __future__ import annotations
"""Load test: 50 concurrent users performing typical operations.

TC-NF-001: P95 response time ≤ 5s, 0 errors 5xx.

Usage:
    locust -f locustfile.py --host http://186.246.31.81 --users 50 --spawn-rate 5 --run-time 15m --headless --csv results
"""

from locust import HttpUser, task, between, events
import json
import random

class TokamakUser(HttpUser):
    wait_time = between(1, 5)

    def on_start(self):
        # Register and login
        email = f"loadtest_{random.randint(10000,99999)}@test.mephi.ru"
        self.client.post("/api/v1/auth/register", json={
            "email": email,
            "password": "loadtest12345",
            "full_name": "Load Test User",
            "consent_given": True,
        })
        res = self.client.post("/api/v1/auth/login", json={
            "email": email,
            "password": "loadtest12345",
        })
        if res.status_code == 200:
            token = res.json()["access_token"]
            self.client.headers["Authorization"] = f"Bearer {token}"
        self.experiment_ids = []

    @task(3)
    def health_check(self):
        self.client.get("/api/v1/health")

    @task(2)
    def list_experiments(self):
        self.client.get("/api/v1/experiments/")

    @task(1)
    def load_experiment(self):
        shot_id = random.choice([30420, 30421, 30422, 30423, 30424])
        res = self.client.post("/api/v1/experiments/load", json={
            "shot_id": shot_id, "source": "mast"
        }, name="/api/v1/experiments/load")
        if res.status_code == 201:
            self.experiment_ids.append(res.json()["id"])

    @task(2)
    def get_experiment(self):
        if self.experiment_ids:
            exp_id = random.choice(self.experiment_ids)
            self.client.get(f"/api/v1/experiments/{exp_id}",
                          name="/api/v1/experiments/[id]")

    @task(2)
    def get_timeseries(self):
        if self.experiment_ids:
            exp_id = random.choice(self.experiment_ids)
            self.client.get(f"/api/v1/experiments/{exp_id}/timeseries",
                          name="/api/v1/experiments/[id]/timeseries")

    @task(1)
    def list_model_runs(self):
        self.client.get("/api/v1/models/runs")

    @task(1)
    def get_privacy_policy(self):
        self.client.get("/api/v1/legal/privacy-policy")

    @task(1)
    def get_user_profile(self):
        self.client.get("/api/v1/auth/me")
