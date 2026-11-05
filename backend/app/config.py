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

    # 大模型：任意 OpenAI 兼容接口（Ollama / DeepSeek / 通义 / Kimi）
    # 用 Ollama 时 key 随便填，Ollama 不校验
    llm_base_url: str = "http://127.0.0.1:11434/v1"
    llm_api_key: str = "ollama"
    llm_model: str = "qwen3.5:latest"
    llm_temperature: float = 0.3
    llm_max_tokens: int = 400
    llm_timeout: float = 120.0
    # 思考型模型（qwen3 系列等）会先输出一大段推理，正文可能被 max_tokens 挤空。
    # 设成 "none" 可以让 Ollama 跳过思考，直接给答案；换别的厂商时置空即可。
    llm_reasoning_effort: str = "none"
    # 带几轮历史进 prompt；0 表示单轮问答（最省 token）
    llm_history_turns: int = 1

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

    @property
    def upload_path(self) -> Path:
        """上传目录绝对路径；.env 里写相对路径时以 backend/ 为基准"""
        p = Path(self.upload_dir)
        return p if p.is_absolute() else ROOT_DIR / p

    @property
    def faiss_index_file(self) -> Path:
        """FAISS 索引文件绝对路径；.env 里写相对路径时以 backend/ 为基准"""
        p = Path(self.faiss_index_path)
        return p if p.is_absolute() else ROOT_DIR / p

    @property
    def embed_model_ref(self) -> str:
        """优先用本地模型目录（离线可用），不存在时才回退到 HuggingFace 模型名。"""
        p = Path(self.embed_model)
        candidate = p if p.is_absolute() else ROOT_DIR / p
        return str(candidate) if candidate.exists() else self.embed_model

    @property
    def llm_chat_url(self) -> str:
        """OpenAI 兼容的对话补全地址，例如 http://127.0.0.1:11434/v1/chat/completions"""
        return self.llm_base_url.rstrip("/") + "/chat/completions"

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()