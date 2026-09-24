from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = "local"

    llm_provider: str = "ollama"
    llm_model: str = "llama3.2:3b"
    ollama_url: str = "http://localhost:11434"

    max_blast_radius: int = 2
    max_retries: int = 2
    tool_timeout_seconds: int = 10

    class Config:
        env_file = ".env"


settings = Settings()
