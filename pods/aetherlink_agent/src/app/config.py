from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    PROM_URL: str = "http://prometheus:9090"
    ALERTMANAGER_URL: str = "http://alertmanager:9093"
    GRAFANA_URL: str = "http://grafana:3000"
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
