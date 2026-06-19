"""
起動時のアップデートチェック。

旧実装は requests を同期的に呼び、KeyErrorしか捕捉していなかった。
ここでは aiohttp(discord.pyが内部で使用)経由で非同期化し、
ネットワークエラー・レート制限・JSON異常系をそれぞれ処理する。
"""
from __future__ import annotations

import logging

import aiohttp

logger = logging.getLogger(__name__)

CURRENT_VERSION = "0.0.1"


async def check_for_update(repository_api_url: str) -> str | None:
    """最新リリースのタグ名を返す。取得できない場合は None。"""
    url = repository_api_url.rstrip("/") + "/releases/latest"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 403:
                    logger.warning(
                        "GitHub APIのレート制限に達したため、更新チェックをスキップします。"
                    )
                    return None
                if resp.status != 200:
                    logger.warning(
                        "更新チェックに失敗しました(HTTP %s)。", resp.status
                    )
                    return None
                data = await resp.json()
    except aiohttp.ClientError as exc:
        logger.warning("更新チェック中にネットワークエラーが発生しました: %s", exc)
        return None
    except TimeoutError:
        logger.warning("更新チェックがタイムアウトしました。")
        return None

    tag_name = data.get("tag_name")
    if tag_name is None:
        logger.warning("更新チェックのレスポンスに tag_name が含まれていません。")
        return None
    return tag_name


def is_newer(latest_tag: str, current: str = CURRENT_VERSION) -> bool:
    """簡易的なセマンティックバージョン比較。'v'プレフィックスを許容する。"""

    def _parse(tag: str) -> tuple[int, ...]:
        cleaned = tag.lstrip("vV")
        parts = []
        for p in cleaned.split("."):
            digits = "".join(ch for ch in p if ch.isdigit())
            parts.append(int(digits) if digits else 0)
        return tuple(parts)

    try:
        return _parse(latest_tag) > _parse(current)
    except (ValueError, AttributeError):
        return False
