"""アプリ設定。環境変数から読み込む。"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # アプリ
    app_name: str = "face_vault"
    debug: bool = False
    # CORS 許可オリジン（カンマ区切り）。Cloudflare Access背後の個人利用前提で緩め
    cors_origins: str = "http://localhost:3017,http://127.0.0.1:3017"

    # DB
    # DATABASE_URL を直接指定すると優先（ローカルは sqlite:///./face_vault.db 等）
    database_url_override: str | None = Field(default=None, alias="DATABASE_URL")
    postgres_host: str = "db"
    postgres_port: int = 5449
    postgres_user: str = "face_vault"
    postgres_password: str = "face_vault"
    postgres_db: str = "face_vault"

    # 顔認識
    face_embedding_dim: int = 512  # ArcFace
    # InsightFace モデルパック（buffalo_l=R50 / antelopev2=R100 高精度）
    face_model_name: str = "antelopev2"
    # 顔検出 信頼度閾値（低いほど小さい/低画質の顔も拾う。既定InsightFaceは0.5）
    face_det_thresh: float = 0.3
    face_det_size: int = 640
    match_threshold: float = Field(
        default=0.35, description="人物照合のコサイン類似度 最小一致閾値（高いほど厳格）"
    )
    # 品質ゲート: 参照ベクトル登録(自動)の最低検出信頼度・最低顔サイズ(px)
    face_min_det_score: float = 0.55
    face_min_px: int = 50
    # 確認キュー: この信頼度未満のマッチは「要確認」に出す
    review_confidence: float = 0.45
    # 統合候補: 別人物のベクトル類似がこれ以上なら統合提案
    merge_suggest_threshold: float = 0.5
    # アップロード時、既存人物に一致しない顔を新規人物として自動登録
    auto_enroll_faces: bool = True
    faiss_index_path: str = "/data/faiss/index.bin"

    # ストレージ
    photo_storage_dir: str = "/data/photos"

    # AI プロバイダ抽象化
    ai_provider: str = "anthropic"  # openai | anthropic | gemini
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    gemini_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    anthropic_model: str = "claude-3-5-haiku-latest"
    gemini_model: str = "gemini-1.5-flash"
    ai_max_tokens: int = 512

    @property
    def database_url(self) -> str:
        if self.database_url_override:
            return self.database_url_override
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
