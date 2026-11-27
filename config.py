from pydantic import SecretStr
from pydantic_settings import SettingsConfigDict, BaseSettings


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # authentication configuration
    secret_key: SecretStr
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # image size configuration
    max_upload_size_bytes: int = 5 * 1024 * 1024  # in MB

    # post per page to load
    posts_per_page: int = 10

    # server reset time for token
    reset_token_expire_minutes: int = 60

    # email configs
    mail_server: str = "localhost"
    mail_port: int = 587
    mail_username = ""
    mail_password: SecretStr = SecretStr("")
    mail_from: str = "noreply@exampl.com"
    mail_use_tls: bool = True

    frontend_url: str = "http://localhost:8000"


settings = Settings()  # type: ignore
