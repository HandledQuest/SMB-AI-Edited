"""
設定管理モジュール。

優先順位: 環境変数 / .env > config/simplemusicbot/config.ini > デフォルト値
トークン類は .env での管理を推奨し、config.ini には保存しない方針に変更。
(旧バージョンは config.ini に平文保存していたが、Git管理下に誤って
 コミットされるリスクを減らすため、機密情報は .env に分離する)
"""
from __future__ import annotations

import configparser
import logging
import os
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

CONFIG_DIR = Path("config") / "simplemusicbot"
CONFIG_FILE = CONFIG_DIR / "config.ini"
CONFIG_VERSION = 7  # 設定スキーマのバージョン(旧config.pyから引き続き使用)


class Settings(BaseSettings):
    """Bot全体の設定。環境変数 > .env > config.ini > デフォルト の順で解決される。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    discord_bot_token: str = Field(default="", description="Discord Botトークン")
    genius_token: str = Field(default="", description="Genius APIトークン(歌詞取得用)")

    default_volume: float = Field(default=0.2, ge=0.0, le=2.0)
    status: str = Field(default="/url | SimpleMusicBot")
    dev_mode: bool = Field(default=False)
    update_check: bool = Field(default=True)
    repository_url: str = Field(
        default="https://api.github.com/repos/HandledQuest/SimpleMusicBot"
    )
    log_level: str = Field(default="INFO")

    @field_validator("discord_bot_token")
    @classmethod
    def _token_not_placeholder(cls, v: str) -> str:
        if v in {"", "YOUR_TOKEN_HERE"}:
            return ""
        return v

    @property
    def is_token_configured(self) -> bool:
        return bool(self.discord_bot_token)


def _load_legacy_ini(path: Path) -> dict:
    """既存の config.ini があれば読み込んでデフォルト値の上書き用辞書を返す。
    トークンも旧形式互換のため読み込むが、.env が優先されるようSettings側で制御する。
    """
    if not path.exists():
        return {}
    parser = configparser.ConfigParser()
    try:
        parser.read(path, encoding="utf-8")
    except UnicodeDecodeError:
        logger.warning(
            "config.ini の文字コードが UTF-8 として読み込めませんでした。"
            "Shift-JIS等の場合は UTF-8 に変換してください。"
        )
        return {}

    if "config" not in parser:
        return {}

    section = parser["config"]
    result = {}
    if "discord_bot_token" in section:
        result["discord_bot_token"] = section.get("discord_bot_token")
    if "genius_token" in section:
        result["genius_token"] = section.get("genius_token")
    if "default_volume" in section:
        result["default_volume"] = section.getfloat("default_volume", fallback=0.2)
    if "status" in section:
        result["status"] = section.get("status")
    if "devmode" in section:
        result["dev_mode"] = section.getboolean("devmode", fallback=False)
    if "updatecheck" in section:
        result["update_check"] = section.getboolean("updatecheck", fallback=True)
    if "repository_url" in section:
        result["repository_url"] = section.get("repository_url")
    return result


def load_settings() -> Settings:
    """設定をロードする。環境変数/.env を優先し、未設定項目だけ config.ini で補完する。"""
    legacy = _load_legacy_ini(CONFIG_FILE)

    # 環境変数で明示的に設定されていない項目だけ legacy 値で補う
    env_keys = {k.lower() for k in os.environ.keys()}
    overrides = {
        k: v
        for k, v in legacy.items()
        if k.upper() not in env_keys and k not in env_keys
    }

    settings = Settings(**overrides)
    return settings


def ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def write_example_env(path: Path = Path(".env.example")) -> None:
    """初回セットアップ用のテンプレートを生成する。"""
    template = (
        "# Discord Developer Portal で取得したBotトークン\n"
        "DISCORD_BOT_TOKEN=YOUR_TOKEN_HERE\n\n"
        "# https://genius.com/api-clients で取得したトークン(歌詞取得機能用、任意)\n"
        "GENIUS_TOKEN=\n\n"
        "DEFAULT_VOLUME=0.2\n"
        "DEV_MODE=false\n"
        "UPDATE_CHECK=true\n"
        "LOG_LEVEL=INFO\n"
    )
    if not path.exists():
        path.write_text(template, encoding="utf-8")
