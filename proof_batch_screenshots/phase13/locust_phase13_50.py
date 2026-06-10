from locust import HttpUser, task, between
from locust.exception import StopUser
import os
import time
import uuid


class P13User(HttpUser):
    wait_time = between(2, 5)

    def on_start(self):
        ts = int(time.time() * 1000)
        email = f"phase13_locust_{ts}_{uuid.uuid4().hex[:8]}@example.com"
        password = "Phase13Temp!123"

        reg = self.client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "username": "loaduser"},
            name="/api/v1/auth/register",
        )
        if reg.status_code not in (200, 201):
            raise StopUser(f"register_failed={reg.status_code} body={reg.text[:200]}")

        token = self.client.post(
            "/api/v1/token",
            data={"username": email, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            name="/api/v1/token",
        )
        if token.status_code != 200:
            raise StopUser(f"token_failed={token.status_code} body={token.text[:200]}")

        self.token = token.json().get("access_token", "")
        if not self.token:
            raise StopUser("token_missing")

    def headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    @task(4)
    def decisions(self):
        self.client.get("/api/v1/decisions", headers=self.headers(), name="/api/v1/decisions")

    @task(4)
    def subscription(self):
        self.client.get("/api/v1/subscription/status", headers=self.headers(), name="/api/v1/subscription/status")

    @task(2)
    def health(self):
        self.client.get("/api/health", headers=self.headers(), name="/api/health")
