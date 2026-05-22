from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = ""
    secret_key: str = ""
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    s3_endpoint: str = "https://storage.googleapis.com"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    gcp_bucket_name: str = "idms-bucket"

    email_encryption_key: str = ""

    opensearch_url: str = "http://opensearch:9200"
    embedding_model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embedding_max_chars: int = 2000
    knn_candidates: int = 20

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        extra="ignore",
    )


settings = Settings()
