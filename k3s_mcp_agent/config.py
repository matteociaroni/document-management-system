from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_name: str = "gemini-2.5-pro"
    base_url: str = "https://litellm-proxy-1013932759942.europe-west8.run.app"
    custom_api_key: str = ""

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    mcp_host: str = "127.0.0.1"
    mcp_port: int = 8001

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        extra="ignore",
    )


settings = Settings()
