from .api_client import APIClient


def main():
    client = APIClient("http://localhost:8000")

    print("Проверка backend:")
    print(client.health_check())

    print("Авторизация:")
    client.login("student", "secure-password")

    print("Текущий пользователь:")
    print(client.get_current_user())


if __name__ == "__main__":
    main()
