from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql://myuser:mypassword@localhost:5432/dms"

    s3_endpoint: str = "http://localhost:8333"
    s3_access_key: str = "mykey"
    s3_secret_key: str = "mysecret"
    gcp_bucket_name: str = "dms-storage"

    # Email encryption (Fernet key)
    email_encryption_key: str = "L2II5RV2sn9EPmWoq1tdfHIN2wwntQfXeKLMG4lPbCc=" # TODO: "change-me-generate-a-real-fernet-key"

    # OAuth2 - Gmail
    google_client_id: str = ""
    google_client_secret: str = ""

    # OAuth2 - Outlook
    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        extra="ignore",
    )


settings = Settings()
