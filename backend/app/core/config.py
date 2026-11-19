from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Smart Student Planner API"
    database_url: str = "postgresql+asyncpg://planner:planner@localhost:5432/smart_student_planner"
    jwt_secret_key: str = Field(
        default="local-development-secret-change-me",
        min_length=32,
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=60, gt=0)
    pnrpu_base_url: str = "https://pstu.ru"
    pnrpu_schedule_path: str = "/student/schedule/"
    pnrpu_request_timeout_seconds: float = Field(default=20, gt=0)
    pnrpu_max_schedule_file_size_bytes: int = Field(default=10 * 1024 * 1024, gt=0)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
