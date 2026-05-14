from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql://myuser:mypassword@localhost:5432/dms"
    s3_endpoint: str = "http://localhost:8333"
    s3_access_key: str = "mykey"
    s3_secret_key: str = "mysecret"
    gcp_bucket_name: str = "dms-storage"

    model_name: str = "claude-sonnet-4-6"
    base_url: str = ""
    custom_api_key: str = ""
    mcp_server_url: str = "http://mcp_server:8001/sse"

    poll_interval_seconds: int = 30
    auto_file_threshold: float = 0.85

    opensearch_url: str = "http://opensearch:9200"
    embedding_model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embedding_dimension: int = 384
    embedding_max_chars: int = 2000

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        extra="ignore",
    )


settings = Settings()
