import time
import requests

BASE = "https://beta.beatvegas.app"
OUT_FILE = "/tmp/phase13_tokens.txt"
COUNT = 50
PASSWORD = "Phase13Temp!123"


def main() -> None:
    with open(OUT_FILE, "w", encoding="utf-8") as out:
        for i in range(COUNT):
            email = f"phase13_pool_{int(time.time()*1000)}_{i}@example.com"
            username = f"pool{i}"
            reg = requests.post(
                f"{BASE}/api/v1/auth/register",
                json={"email": email, "password": PASSWORD, "username": username},
                timeout=30,
            )
            reg.raise_for_status()
            tok = requests.post(
                f"{BASE}/api/v1/token",
                data={"username": email, "password": PASSWORD},
                timeout=30,
            )
            tok.raise_for_status()
            out.write(tok.json()["access_token"] + "\n")

    print(f"TOKENS_READY={COUNT}")
    print(f"TOKENS_FILE={OUT_FILE}")


if __name__ == "__main__":
    main()
