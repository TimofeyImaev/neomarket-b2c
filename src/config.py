from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_ttl_seconds: int = 3600

    database_url: str = "sqlite+pysqlite:///:memory:"

    b2b_base_url: str = "http://localhost:8001"
    b2b_service_key: str = "dev-service-key"

    idempotency_ttl_seconds: int = 3600


settings = Settings()
