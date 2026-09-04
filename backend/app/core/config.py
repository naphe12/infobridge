from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://infobridge:infobridge_dev_password@localhost:5432/infobridge"
    api_cors_origins: str = "http://localhost:5173,https://infobridge-frontend-production.up.railway.app"
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    lifecycle_scan_interval_seconds: int = 3600
    auto_archive_after_days: int = 30
    default_retention_days: int = 3650
    document_storage_path: str = "storage/documents"
    document_encryption_key: str | None = None
    document_max_upload_bytes: int = 25 * 1024 * 1024
    document_allowed_mime_types: str = (
        "application/pdf,"
        "image/png,"
        "image/jpeg,"
        "text/plain,"
        "text/csv,"
        "application/json,"
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document,"
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
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

    @property
    def allowed_document_mime_types(self) -> set[str]:
        return {mime_type.strip() for mime_type in self.document_allowed_mime_types.split(",") if mime_type.strip()}


settings = Settings()
