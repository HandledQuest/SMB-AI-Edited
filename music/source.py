"""
yt-dlp呼び出しを非同期化するモジュール。

旧実装は `YoutubeDL.extract_info` をイベントループ上で同期実行しており、
動画情報の取得中はBot全体(他ギルドの応答も含む)がブロックされていた。
ここでは `loop.run_in_executor` でスレッドプールに逃がし、ブロッキングを防ぐ。
"""
from __future__ import annotations

import asyncio
import functools
import logging
import re
from dataclasses import dataclass

from yt_dlp import YoutubeDL

logger = logging.getLogger(__name__)

YDL_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "default_search": "auto",
    "source_address": "0.0.0.0",
}

# http(s)以外、または明らかにローカル/内部ネットワークを指すホストへの
# 直リンクを弾くための簡易チェック。SSRF対策として最低限のフィルタ。
_ALLOWED_SCHEMES = ("http://", "https://")
_BLOCKED_HOST_PATTERNS = (
    r"^localhost$",
    r"^127\.",
    r"^0\.0\.0\.0$",
    r"^10\.",
    r"^192\.168\.",
    r"^169\.254\.",
    r"^172\.(1[6-9]|2\d|3[0-1])\.",
    r"^\[?::1\]?$",
)


class InvalidURLError(ValueError):
    """ユーザー入力のURLが不正、または許可されないホストを指す場合に発生する。"""


class ExtractionError(RuntimeError):
    """yt-dlpによる情報抽出に失敗した場合に発生する。"""


def validate_url(url: str) -> None:
    """最低限のURL検証。スキーム確認とプライベートIP/localhostの拒否を行う。"""
    if not url.lower().startswith(_ALLOWED_SCHEMES):
        raise InvalidURLError("URLはhttp(s)で始まる必要があります。")

    host_match = re.match(r"https?://([^/:]+)", url, re.IGNORECASE)
    if not host_match:
        raise InvalidURLError("URLからホスト名を解析できませんでした。")
    host = host_match.group(1)

    for pattern in _BLOCKED_HOST_PATTERNS:
        if re.match(pattern, host):
            raise InvalidURLError("内部/ローカルアドレスへのアクセスは許可されていません。")


@dataclass(frozen=True)
class TrackInfo:
    title: str
    webpage_url: str
    stream_url: str
    duration: float | None = None


def _extract_sync(query: str, *, is_search: bool) -> dict:
    target = f"ytsearch1:{query}" if is_search else query
    with YoutubeDL(YDL_OPTIONS) as ydl:
        info = ydl.extract_info(target, download=False)
    if is_search:
        entries = info.get("entries") or []
        if not entries:
            raise ExtractionError("検索結果が見つかりませんでした。")
        info = entries[0]
    return info


async def extract_track(
    query: str,
    *,
    is_search: bool = False,
    loop: asyncio.AbstractEventLoop | None = None,
) -> TrackInfo:
    """yt-dlpでの情報抽出を別スレッドで実行し、イベントループをブロックしない。"""
    if not is_search:
        validate_url(query)

    loop = loop or asyncio.get_running_loop()
    try:
        info = await loop.run_in_executor(
            None, functools.partial(_extract_sync, query, is_search=is_search)
        )
    except Exception as exc:  # yt_dlp.utils.DownloadError 等
        logger.exception("yt-dlpでの情報抽出に失敗しました: %s", query)
        raise ExtractionError(f"再生情報の取得に失敗しました: {exc}") from exc

    stream_url = info.get("url")
    if not stream_url:
        raise ExtractionError("再生用のストリームURLを取得できませんでした。")

    return TrackInfo(
        title=info.get("title", "不明なタイトル"),
        webpage_url=info.get("webpage_url", query),
        stream_url=stream_url,
        duration=info.get("duration"),
    )
