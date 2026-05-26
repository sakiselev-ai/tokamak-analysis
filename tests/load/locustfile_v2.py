from __future__ import annotations
"""Load test TC-NF-001 v2: 50 concurrent users, pre-authenticated.

Uses a single shared admin account to avoid bcrypt bottleneck on registration.
Tests API endpoints under load.

Usage:
    locust -f locustfile_v2.py --host https://tokamak-ai.ru \
        --users 50 --spawn-rate 10 --run-time 5m --headless \
        --csv results/load_test_v2
"""

from locust import HttpUser, task, between
import random


class TokamakUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        res = self.client.post("/api/v1/auth/login", json={
            "email": "admin@mephi.ru",
            "password": "admin123",
        })
        if res.status_code == 200:
            token = res.json()["access_token"]
            self.client.headers["Authorization"] = f"Bearer {token}"

    @task(5)
    def health_check(self):
        self.client.get("/api/v1/health")

    @task(3)
    def list_experiments(self):
        self.client.get("/api/v1/experiments/")

    @task(3)
    def list_models(self):
        self.client.get("/api/v1/models/")

    @task(2)
    def list_runs(self):
        self.client.get("/api/v1/models/runs")

    @task(2)
    def get_profile(self):
        self.client.get("/api/v1/auth/me")

    @task(2)
    def privacy_policy(self):
        self.client.get("/api/v1/legal/privacy-policy")

    @task(1)
    def classify(self):
        self.client.post("/api/v1/predictions/classify",
                        json={"experiment_id": 1},
                        name="/api/v1/predictions/classify")

    @task(1)
    def disruption(self):
        self.client.post("/api/v1/predictions/disruption",
                        json={"experiment_id": 1},
                        name="/api/v1/predictions/disruption")

    @task(1)
    def export_csv(self):
        self.client.get("/api/v1/experiments/1/export?format=csv",
                       name="/api/v1/experiments/[id]/export")
