from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://myuser:mypassword@localhost:5432/dms"
    secret_key: str = "your-secret-key-change-in-prod"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    s3_endpoint: str = "http://localhost:8333"
    s3_access_key: str = "mykey"
    s3_secret_key: str = "mysecret"
    
    class Config:
        env_file = ".env"


settings = Settings()
