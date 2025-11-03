from __future__ import annotations

import os
from pydantic_settings import BaseSettings
from pydantic import Field
from dotenv import load_dotenv


load_dotenv()


class Settings(BaseSettings):
    DB_URL: str = Field(default=os.getenv("DB_URL", "sqlite:///./app.db"))
    JWT_SECRET: str = Field(default=os.getenv("JWT_SECRET", "change_me"))
    JWT_ALG: str = Field(default=os.getenv("JWT_ALG", "HS256"))
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    )

    class Config:
        case_sensitive = False


settings = Settings()
