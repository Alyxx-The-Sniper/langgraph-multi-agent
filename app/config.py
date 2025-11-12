# app/config.py
from pydantic import ConfigDict  
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Loads all environment variables"""
    DEEPINFRA_API_KEY: str
    AIRTABLE_BASE_ID: str
    AIRTABLE_TOKEN: str
    SLACK_WEBHOOK_URL: str
    
    model_config = ConfigDict(
        env_file="app/.env",
        env_file_encoding="utf-8"
    )

# Create a single instance to import in other files
settings = Settings()

print("✅ Credentials loaded (Airtable, Slack, DeepInfra)")