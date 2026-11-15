from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:1.7b"
    ollama_code_model: str = "qwen2.5-coder:3b"
    database_url: str = "sqlite:///./csrgo_video_studio.db"
    host: str = "127.0.0.1"
    port: int = 8000
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
