from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import os

repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
default_sqlite_path = os.path.join(repo_root, "prism.db").replace("\\", "/")

class Settings(BaseSettings):
    PRISM_ENV: str = "demo"
    DATABASE_URL: str = f"sqlite:///{default_sqlite_path}"
    
    JWT_SECRET: str = "dev_secret_for_sih_prototype_only_change_in_production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    
    PRISM_TIMEZONE: str = "Asia/Kolkata"
    CONFIG_VERSION: str = "demo-1.0"
    SNAPSHOT_POLICY: str = "strict"
    LOG_LEVEL: str = "INFO"
    WORKER_CONCURRENCY: int = 1
    CORS_ORIGINS: str = "http://localhost:3000"
    
    # Computational Coordinate Reference System (UTM Zone 43N by default)
    COMPUTATIONAL_CRS: str = "EPSG:32643"
    @property
    def resolved_database_url(self) -> str:
        if self.DATABASE_URL.startswith("sqlite:///./"):
            rel_file = self.DATABASE_URL.replace("sqlite:///./", "")
            return f"sqlite:///{os.path.join(repo_root, rel_file).replace('\\', '/')}"
        return self.DATABASE_URL

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_runtime_security(self):
        production = self.PRISM_ENV.lower() in {"prod", "production", "staging"}
        if production and (
            self.JWT_SECRET == "dev_secret_for_sih_prototype_only_change_in_production"
            or len(self.JWT_SECRET) < 32
        ):
            raise ValueError("JWT_SECRET must be a unique value of at least 32 characters outside demo/test environments")
        if "*" in self.cors_origins and production:
            raise ValueError("Wildcard CORS_ORIGINS is prohibited outside demo/test environments")
        return self


    model_config = SettingsConfigDict(
        env_file=os.path.join(repo_root, ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
