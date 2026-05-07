from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql://myuser:mypassword@localhost:5432/dms"
    host: str = "0.0.0.0"
    port: int = 8001

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        extra="ignore",
    )


settings = Settings()
