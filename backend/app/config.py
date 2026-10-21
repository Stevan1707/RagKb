from urllib.parse import quote_plus
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent  # backend/



class Settings(BaseSettings):
    """所有可调参数的唯一来源，通过环境变量或 .env 覆盖。"""

    app_name: str = "RagKb API"
    debug: bool = True

    host: str = "127.0.0.1"
    port: int = 8000

    api_prefix: str = "/api"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # 数据库
    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = ""
    db_name: str = "ragkb"

    # 检索 / 入库参数（第 1 步用）
    chunk_size: int = 500
    chunk_overlap: int = 80
    top_k: int = 5
    embed_model: str = "BAAI/bge-small-zh-v1.5"
    upload_dir: str = "data/uploads"
    faiss_index_path: str = "data/faiss.index"

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def async_database_url(self) -> str:
        pwd = quote_plus(self.db_password)   # 密码含 @ # / 时不会把 URL 解析坏
        return (
            f"mysql+aiomysql://{self.db_user}:{pwd}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()