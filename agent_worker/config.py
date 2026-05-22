from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = ""
    s3_endpoint: str = "https://storage.googleapis.com"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    gcp_bucket_name: str = "idms-bucket"

    model_name: str = "gemini-2.5-pro"
    base_url: str = "https://litellm-proxy-1013932759942.europe-west8.run.app"
    custom_api_key: str = ""
    mcp_server_url: str = "http://mcp-server:8001/sse"

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
