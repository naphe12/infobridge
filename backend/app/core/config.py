from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://infobridge:infobridge_dev_password@localhost:5432/infobridge"
    api_cors_origins: str = "http://localhost:5173,https://infobridge-frontend-production.up.railway.app"
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 15
    document_storage_path: str = "storage/documents"
    document_encryption_key: str | None = None
    railway_volume_mount_path: str | None = None

    model_config = SettingsConfigDict(env_file="../.env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.api_cors_origins.split(",") if origin.strip()]

    @property
    def effective_document_storage_path(self) -> str:
        if self.document_storage_path != "storage/documents":
            return self.document_storage_path
        return self.railway_volume_mount_path or self.document_storage_path


settings = Settings()
