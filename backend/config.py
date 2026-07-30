from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment or .env via pydantic."""

    EMBEDDING_MODEL: str = Field(..., env="EMBEDDING_MODEL")
    LLM_API_KEY: str = Field(..., env="LLM_API_KEY")
    LLM_URL: str | None = Field(None, env="LLM_URL")

    # Processing tunables
    BATCH_PAGES: int = Field(10, env="BATCH_PAGES")
    CHUNK_SIZE: int = Field(1000, env="CHUNK_SIZE")
    CHUNK_OVERLAP: int = Field(200, env="CHUNK_OVERLAP")
    # Tokenization heuristics for dynamic chunk sizing
    MAX_TOKENS_PER_CHUNK: int = Field(500, env="MAX_TOKENS_PER_CHUNK")
    TOKEN_CHAR_RATIO: int = Field(4, env="TOKEN_CHAR_RATIO")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }
