from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://mlplatform:mlplatform_secret@localhost:5432/mlplatform"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440  # 24 hours

    # Admin credentials (single-user mode)
    admin_email: str = "admin@mlplatform.dev"
    admin_password: str = "admin_secret"

    # Inference containers
    inference_host: str = "localhost"  # override to container hostname in Docker

    # Storage
    artifact_store_path: str = "./artifacts"

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def artifact_store_abs_path(self) -> str:
        """Always return an absolute path for volume mounts."""
        from pathlib import Path
        return str(Path(self.artifact_store_path).resolve())

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
