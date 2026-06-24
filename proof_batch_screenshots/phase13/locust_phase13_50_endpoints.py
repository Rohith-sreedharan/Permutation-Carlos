from locust import HttpUser, task, between
from locust.exception import StopUser
import os
import random


TOKENS_PATH = os.getenv("TOKENS_PATH", "/tmp/phase13_tokens.txt")
TOKENS = []


class P13User(HttpUser):
    wait_time = between(3, 6)

    def on_start(self):
        global TOKENS
        if not TOKENS:
            if not os.path.exists(TOKENS_PATH):
                raise StopUser(f"tokens_file_missing={TOKENS_PATH}")
            with open(TOKENS_PATH, "r", encoding="utf-8") as f:
                TOKENS = [line.strip() for line in f if line.strip()]
            if not TOKENS:
                raise StopUser("tokens_file_empty")
        self.token = random.choice(TOKENS)

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
