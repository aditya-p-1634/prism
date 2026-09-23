from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import os

repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
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
    
    # Computational Coordinate Reference System (UTM Zone 43N by default)
    COMPUTATIONAL_CRS: str = "EPSG:32643"
    STORAGE_CRS: str = "EPSG:4326"

    model_config = SettingsConfigDict(
        env_file=os.path.join(repo_root, ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
