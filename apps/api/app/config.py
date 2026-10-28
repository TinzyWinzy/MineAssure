from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = (
        "postgresql+psycopg://mineassure:mineassure@localhost:5432/mineassure"
    )
    secret_key: str = "change-me"
    signing_key_secret: str | None = None
    environment: str = "development"
    api_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:5173"
    worker_in_process: bool = False
    worker_poll_seconds: int = 15

    @model_validator(mode="after")
    def _require_secrets_in_production(self):
        if self.environment == "production":
            if self.secret_key == "change-me":
                raise ValueError("secret_key must be set in production")
            if not self.signing_key_secret or self.signing_key_secret == "change-me":
                raise ValueError("signing_key_secret must be set in production")
            if self.signing_key_secret == self.secret_key:
                raise ValueError(
                    "signing_key_secret must differ from secret_key; session and "
                    "signature key material must not share one secret"
                )
            if "mineassure:mineassure@" in self.database_url:
                raise ValueError(
                    "default database credentials must not be used in production"
                )
        return self


settings = Settings()
