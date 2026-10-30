import httpx


class APIClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.token = None

    def health_check(self):
        response = httpx.get(
            f"{self.base_url}/health",
            trust_env=False,
        )
        response.raise_for_status()
        return response.json()

    def login(self, username: str, password: str):
        response = httpx.post(
            f"{self.base_url}/api/v1/auth/login",
            json={
                "identifier": username,
                "password": password,
            },
            trust_env=False,
        )
        response.raise_for_status()

        data = response.json()
        self.token = data["access_token"]

        return data

    def get_current_user(self):
        if not self.token:
            raise RuntimeError("Сначала необходимо выполнить login")

        response = httpx.get(
            f"{self.base_url}/api/v1/users/me",
            headers={
                "Authorization": f"Bearer {self.token}"
            },
            trust_env=False,
        )
        response.raise_for_status()

        return response.json()
