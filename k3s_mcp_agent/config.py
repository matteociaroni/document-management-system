from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # LLM config (matching the existing agent)
    model_name: str = "claude-sonnet-4-6"
    base_url: str = ""
    custom_api_key: str = ""
    
    # Telegram config
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    
    # MCP server config
    mcp_host: str = "127.0.0.1"
    mcp_port: int = 8001
    
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        extra="ignore",
    )

settings = Settings()
