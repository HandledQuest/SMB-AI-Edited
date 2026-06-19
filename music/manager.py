"""
ギルドごとの再生状態を管理するモジュール。

旧実装はモジュールレベルの `queue`/`nop` リストを全ギルドで共有していたため、
複数サーバーで同時利用すると再生キューが混ざってしまっていた。
ここでは `GuildPlayer` をギルドIDごとに保持することで状態を分離する。
"""
from __future__ import annotations

import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field

import discord

from music.source import ExtractionError, TrackInfo, extract_track

logger = logging.getLogger(__name__)


@dataclass
class GuildPlayer:
    guild_id: int
    voice_client: discord.VoiceClient | None = None
    queue: deque[str] = field(default_factory=deque)
    history: deque[TrackInfo] = field(default_factory=lambda: deque(maxlen=20))
    now_playing: TrackInfo | None = None
    volume: float = 0.2
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def is_playing(self) -> bool:
        return bool(self.voice_client and self.voice_client.is_playing())

    def enqueue(self, query: str) -> int:
        """キューに追加し、追加後の位置(1始まり)を返す。"""
        self.queue.append(query)
        return len(self.queue)

    def remove_at(self, position: int) -> str:
        """1始まりの位置を指定してキューから削除する。範囲外なら IndexError。"""
        index = position - 1
        if index < 0 or index >= len(self.queue):
            raise IndexError(f"指定された位置 {position} はキューの範囲外です。")
        items = list(self.queue)
        removed = items.pop(index)
        self.queue = deque(items)
        return removed

    def snapshot_queue(self) -> list[str]:
        return list(self.queue)

    async def play_next(self, bot_loop: asyncio.AbstractEventLoop) -> None:
        """キューの先頭を再生する。再生終了時に自動で次の曲へ進む。"""
        async with self._lock:
            if not self.queue:
                self.now_playing = None
                if self.voice_client and self.voice_client.is_connected():
                    # キューが空になったら何もしない(自動切断は呼び出し側の判断に委ねる)
                    pass
                return

            query = self.queue.popleft()

        try:
            track = await extract_track(query, is_search=False)
        except ExtractionError:
            logger.warning("再生に失敗したためスキップします: %s", query)
            await self.play_next(bot_loop)
            return

        self.now_playing = track
        self.history.append(track)

        if self.voice_client is None:
            logger.error("ボイスクライアントが存在しないため再生できません。")
            return

        source = discord.FFmpegPCMAudio(
            track.stream_url,
            before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            options="-vn",
        )
        transformed = discord.PCMVolumeTransformer(source, volume=self.volume)

        def _after_play(error: Exception | None) -> None:
            if error:
                logger.error("再生中にエラーが発生しました: %s", error)
            asyncio.run_coroutine_threadsafe(self.play_next(bot_loop), bot_loop)

        self.voice_client.play(transformed, after=_after_play)

    async def enqueue_and_play_if_idle(
        self, query: str, bot_loop: asyncio.AbstractEventLoop
    ) -> int:
        position = self.enqueue(query)
        if not self.is_playing():
            await self.play_next(bot_loop)
        return position

    def stop(self) -> None:
        self.queue.clear()
        self.now_playing = None
        if self.voice_client:
            self.voice_client.stop()

    def skip(self) -> None:
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.stop()  # after コールバックが次の曲を呼ぶ

    def set_volume(self, percent: float, default_volume: float) -> float:
        new_volume = max(0.0, percent / 100 * default_volume)
        self.volume = new_volume
        if self.voice_client and isinstance(
            self.voice_client.source, discord.PCMVolumeTransformer
        ):
            self.voice_client.source.volume = new_volume
        return new_volume


class GuildPlayerManager:
    """ギルドID -> GuildPlayer の対応を管理するレジストリ。"""

    def __init__(self, default_volume: float) -> None:
        self._players: dict[int, GuildPlayer] = {}
        self._default_volume = default_volume

    def get_or_create(self, guild_id: int) -> GuildPlayer:
        if guild_id not in self._players:
            self._players[guild_id] = GuildPlayer(
                guild_id=guild_id, volume=self._default_volume
            )
        return self._players[guild_id]

    def get(self, guild_id: int) -> GuildPlayer | None:
        return self._players.get(guild_id)

    def remove(self, guild_id: int) -> None:
        self._players.pop(guild_id, None)
