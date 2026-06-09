"""
BeatVegas Load Test — locust
Usage:
  locust -f scripts/load_test.py --host https://beta.beatvegas.app \
         --headless -u 100 -r 10 --run-time 60s
  locust -f scripts/load_test.py --host https://beta.beatvegas.app \
         --headless -u 500 -r 25 --run-time 60s
  locust -f scripts/load_test.py --host https://beta.beatvegas.app \
         --headless -u 1000 -r 50 --run-time 60s
"""
import os
from locust import HttpUser, task, between


class BeatVegasUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        """Use legacy test token accepted by subscription route in this environment."""
        self.token = os.getenv("LOAD_TEST_TOKEN", "user:6a2232b23130dcedc28644f7")

    def _auth_headers(self):
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    @task(5)
    def dashboard_events(self):
        self.client.get(
            "/api/v1/odds/list?date=2026-06-06&upcoming_only=false&limit=50",
            headers=self._auth_headers(),
            name="/api/v1/odds/list",
        )

    @task(3)
    def subscription_status(self):
        self.client.get(
            "/api/v1/subscription/status",
            headers=self._auth_headers(),
            name="/api/v1/subscription/status",
        )

    @task(2)
    def predictions(self):
        self.client.get(
            "/docs",
            headers=self._auth_headers(),
            name="/docs",
        )

    @task(1)
    def health_check(self):
        self.client.get("/docs", name="/docs")
