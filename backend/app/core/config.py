from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    PROJECT_NAME: str = "NetGuard AI"
    VERSION: str = "0.1.0"
    API_PREFIX: str = "/api/v1"
    
    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "production")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # Database - All from environment variables with safe defaults for backward compatibility
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "password")
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "db")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "netguard")
    
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        
    # Security - All from environment variables with safe defaults
    SECRET_KEY: str = os.getenv("SECRET_KEY", "supersecretkey")  # Backward compatible default
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

    # WireGuard - All from environment variables
    WG_SERVER_PUBLIC_KEY: str = os.getenv("WG_SERVER_PUBLIC_KEY", "SERVER_PUBLIC_KEY_PLACEHOLDER")
    WG_SERVER_ENDPOINT: str = os.getenv("WG_SERVER_ENDPOINT", "74.208.167.166")
    WG_SERVER_PORT: int = int(os.getenv("WG_SERVER_PORT", "51820"))
    
    # CORS Configuration
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "https://app.netguard.fun,https://www.netguard.fun")
    
    # Encryption Key for database field encryption
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "")
    
    @property
    def CORS_ORIGINS_LIST(self) -> list:
        """Parse CORS_ORIGINS string into list, with fallback to allow all if not set"""
        if not self.CORS_ORIGINS:
            return ["*"]  # Fallback for backward compatibility
        origins = [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
        # Add localhost for development if DEBUG is enabled
        if self.DEBUG:
            origins.extend(["http://localhost:3000", "http://localhost:5173"])
        return origins

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
