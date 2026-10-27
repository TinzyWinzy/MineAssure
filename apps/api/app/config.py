from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = (
        "postgresql+psycopg://mineassure:mineassure@localhost:5432/mineassure"
    )
    secret_key: str = "change-me"
    environment: str = "development"
    api_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:5173"

    @model_validator(mode="after")
    def _require_secrets_in_production(self):
        if self.environment == "production":
            if self.secret_key == "change-me":
                raise ValueError("secret_key must be set in production")
            if "mineassure:mineassure@" in self.database_url:
                raise ValueError(
                    "default database credentials must not be used in production"
                )
        return self


settings = Settings()
