from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    database_url: str = Field(default='postgresql+psycopg://postgres:postgres@localhost:5432/plan_gastos')
    postgres_db: str = Field(default='plan_gastos')
    postgres_user: str = Field(default='postgres')
    postgres_password: str = Field(default='postgres')
    postgres_host: str = Field(default='localhost')
    postgres_port: int = Field(default=5432)
    firebase_project_id: str | None = Field(default=None)
    firebase_client_email: str | None = Field(default=None)
    firebase_private_key: str | None = Field(default=None)
    cors_allowed_origins: list[str] = Field(default=['http://localhost:4200'])


settings = Settings()
