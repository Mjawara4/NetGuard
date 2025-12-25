from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "NetGuard AI"
    VERSION: str = "0.1.0"
    API_PREFIX: str = "/api/v1"
    
    # Database
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "password"
    POSTGRES_SERVER: str = "db"
    POSTGRES_PORT: str = "5432"
    POSTGRES_DB: str = "netguard"
    
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        
    # Security
    SECRET_KEY: str = "supersecretkey" # Change in production
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # WireGuard
    WG_SERVER_PUBLIC_KEY: str = "SERVER_PUBLIC_KEY_PLACEHOLDER"
    WG_SERVER_ENDPOINT: str = "74.208.192.189" # VPS IP
    WG_SERVER_PORT: int = 51820

    
    class Config:
        env_file = ".env"

settings = Settings()
