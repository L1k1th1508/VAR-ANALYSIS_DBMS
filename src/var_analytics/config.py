from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    reader_database_url: str = ""
    admin_database_url: str = ""
    admin_password_hash: str = ""


def settings() -> Settings:
    return Settings()
