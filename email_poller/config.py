from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = ""

    s3_endpoint: str = "https://storage.googleapis.com"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    gcp_bucket_name: str = "idms-bucket"

    email_encryption_key: str = ""

    google_client_id: str = ""
    google_client_secret: str = ""

    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        extra="ignore",
    )


settings = Settings()
