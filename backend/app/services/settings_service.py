"""Dynamic application settings.

Precedence: DB override > environment/default settings. Connection settings that
are required before the DB is available are intentionally not editable here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.app_setting import AppSetting

base_settings = get_settings()


@dataclass(frozen=True)
class SettingSpec:
    key: str
    label: str
    type: str  # "str" | "int" | "float" | "secret" | "bool"
    group: str


SPECS: list[SettingSpec] = [
    SettingSpec("ai_provider", "AIプロバイダ (openai|anthropic|gemini)", "str", "AI"),
    SettingSpec("anthropic_api_key", "Anthropic APIキー", "secret", "AI"),
    SettingSpec("openai_api_key", "OpenAI APIキー", "secret", "AI"),
    SettingSpec("gemini_api_key", "Gemini APIキー", "secret", "AI"),
    SettingSpec("anthropic_model", "Anthropic モデル", "str", "AI"),
    SettingSpec("openai_model", "OpenAI モデル", "str", "AI"),
    SettingSpec("gemini_model", "Gemini モデル", "str", "AI"),
    SettingSpec("ai_max_tokens", "AI 最大トークン", "int", "AI"),
    SettingSpec("match_threshold", "InsightFace 顔照合しきい値", "float", "顔認識"),
    SettingSpec("face01_enabled", "Face01 / JAPANESE FACE V1 を有効化", "bool", "顔認識"),
    SettingSpec("face01_model_path", "Face01 ONNXモデルパス", "str", "顔認識"),
    SettingSpec("face01_threshold", "Face01 顔照合しきい値", "float", "顔認識"),
    SettingSpec("auto_enroll_faces", "未一致の顔を新規人物として自動登録", "bool", "顔認識"),
    SettingSpec("face_min_det_score", "品質ゲート 最低検出信頼度", "float", "顔認識"),
    SettingSpec("face_min_px", "品質ゲート 最低顔サイズ(px)", "int", "顔認識"),
    SettingSpec("review_confidence", "確認キュー 信頼度しきい値", "float", "顔認識"),
    SettingSpec("merge_suggest_threshold", "統合候補 類似しきい値", "float", "顔認識"),
    SettingSpec("faiss_index_path", "FAISS インデックスパス", "str", "顔認識"),
    SettingSpec("photo_storage_dir", "写真保存ディレクトリ", "str", "ストレージ"),
]
SPEC_BY_KEY = {s.key: s for s in SPECS}


def _cast(spec: SettingSpec, raw: str) -> Any:
    if spec.type == "int":
        return int(raw)
    if spec.type == "float":
        return float(raw)
    if spec.type == "bool":
        return str(raw).strip().lower() in ("1", "true", "yes", "on")
    return raw


class SettingsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _overrides(self) -> dict[str, str | None]:
        rows = self.db.execute(select(AppSetting.key, AppSetting.value)).all()
        return {k: v for k, v in rows}

    def value(self, key: str) -> Any:
        spec = SPEC_BY_KEY.get(key)
        ov = self._overrides().get(key)
        if ov is not None and ov != "":
            return _cast(spec, ov) if spec else ov
        return getattr(base_settings, key, None)

    def all_items(self) -> list[dict[str, Any]]:
        ov = self._overrides()
        items: list[dict[str, Any]] = []
        for spec in SPECS:
            raw = ov.get(spec.key)
            has_override = raw is not None and raw != ""
            effective = raw if has_override else getattr(base_settings, spec.key, None)
            if spec.type == "secret":
                value = ""
            elif spec.type == "bool":
                value = "true" if _cast(spec, str(effective)) else "false"
            else:
                value = str(effective) if effective is not None else ""
            items.append(
                {
                    "key": spec.key,
                    "label": spec.label,
                    "type": spec.type,
                    "group": spec.group,
                    "value": value,
                    "is_set": effective not in (None, ""),
                    "source": "db" if has_override else "env/default",
                }
            )
        return items

    def update(self, values: dict[str, str | None]) -> None:
        for key, val in values.items():
            if key not in SPEC_BY_KEY:
                continue
            row = self.db.get(AppSetting, key)
            if val is None or val == "":
                if row is not None:
                    self.db.delete(row)
                continue
            if row is None:
                self.db.add(AppSetting(key=key, value=val))
            else:
                row.value = val
        self.db.commit()
