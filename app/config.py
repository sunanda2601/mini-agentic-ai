from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator


class Settings(BaseSettings):
    app_env: str = "local"

    llm_provider: str = "ollama"
    llm_model: str = "llama3.2:3b"
    ollama_url: str = "http://localhost:11434"

    max_blast_radius: int = 2
    max_retries: int = 2
    tool_timeout_seconds: int = 10
    approval_api_key: str = ""

    model_config = SettingsConfigDict(env_file=".env")

    @model_validator(mode="after")
    def validate_production_security(self):
        if (
            self.app_env.lower() == "production"
            and not self.approval_api_key.strip()
        ):
            raise ValueError(
                "APPROVAL_API_KEY must be configured in production."
            )
        return self


settings = Settings()