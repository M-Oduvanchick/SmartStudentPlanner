from .api_client import APIClient


def main():
    client = APIClient("http://localhost:8000")
    print(client.health_check())


if __name__ == "__main__":
    main()
