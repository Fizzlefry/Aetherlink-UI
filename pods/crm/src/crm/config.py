from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """CRM application settings."""
    
    DATABASE_URL: str = "postgresql+psycopg://crm:crm@postgres-crm:5432/crm"
    CRM_ENABLE_SEED: bool = False
    LOG_LEVEL: str = "INFO"
    
    # JWT settings
    JWT_SECRET_KEY: str = "your-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # MinIO settings
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str = "admin"
    MINIO_SECRET_KEY: str = "admin123"
    MINIO_BUCKET: str = "crm-files"
    MINIO_USE_SSL: bool = False
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
