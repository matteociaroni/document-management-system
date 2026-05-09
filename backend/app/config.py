from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://myuser:mypassword@localhost:5432/dms"
    secret_key: str = "your-secret-key-change-in-prod"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    s3_endpoint: str = "http://localhost:8333"
    s3_access_key: str = "mykey"
    s3_secret_key: str = "mysecret"

    # Email encryption (Fernet key, generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    email_encryption_key: str = "change-me-generate-a-real-fernet-key"

    # Agent settings
    agent_confidence_threshold: float = 0.75
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"

    # OAuth2 - Gmail
    google_client_id: str = ""
    google_client_secret: str = ""

    # OAuth2 - Outlook
    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""

    # OpenSearch
    opensearch_url: str = "http://opensearch:9200"

    # Embeddings
    embedding_model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embedding_max_chars: int = 2000
    knn_candidates: int = 20

    class Config:
        env_file = ".env"


settings = Settings()
