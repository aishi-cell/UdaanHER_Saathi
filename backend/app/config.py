from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    sarvam_api_key: str = Field(validation_alias="SARVAM_API_KEY")
    openai_api_key: str = Field(validation_alias="OPENAI_API_KEY")
    openai_model: str = Field(validation_alias="OPENAI_MODEL")
    tts_speaker: str = Field(validation_alias="TTS_SPEAKER")
    default_language: str = Field(validation_alias="DEFAULT_LANGUAGE")
    database_url: str = Field(validation_alias="DATABASE_URL")
    cors_origins: str = Field(validation_alias="CORS_ORIGINS")
    # Optional: enables the Content Builder's YouTube search (plan v2 slow
    # lane). Without it the builder still runs, but distills ungrounded.
    youtube_api_key: str | None = Field(default=None, validation_alias="YOUTUBE_API_KEY")


def get_settings() -> Settings:
    try:
        return Settings()
    except Exception as exc:
        missing = [
            err["loc"][0]
            for err in getattr(exc, "errors", lambda: [])()
            if err.get("type") == "missing"
        ]
        if missing:
            raise RuntimeError(
                f"Missing required environment variable(s): {', '.join(missing)}. "
                "Copy .env.example to backend/.env and fill in real values."
            ) from None
        raise RuntimeError("Invalid configuration in backend/.env.") from None
