"""音楽再生関連のスラッシュコマンド群。"""
import logging
from typing import Optional

import discord
from discord.ext import commands

from errors import safe_respond
from music.manager import GuildPlayerManager
from music.source import ExtractionError, InvalidURLError, extract_track

logger = logging.getLogger(__name__)


class PlaybackCog(commands.Cog):
    def __init__(self, bot: discord.Bot, player_manager: GuildPlayerManager) -> None:
        self.bot = bot
        self.player_manager = player_manager

    async def _ensure_voice_connection(
        self, ctx: discord.ApplicationContext
    ) -> Optional[discord.VoiceClient]:
        if ctx.voice_client is not None:
            return ctx.voice_client

        author_voice = getattr(ctx.author, "voice", None)
        if author_voice is None or author_voice.channel is None:
            await safe_respond(
                ctx, ":warning: ボイスチャンネルに接続してから実行してください!"
            )
            return None

        return await author_voice.channel.connect()

    @commands.slash_command(name="url", description="指定したURLの音楽を再生します。")
    async def play_url(self, ctx: discord.ApplicationContext, url: str) -> None:
        await ctx.defer()  # VC接続/yt-dlp抽出は3秒を超えうるため先にdeferする

        try:
            from music.source import validate_url

            validate_url(url)
        except InvalidURLError as exc:
            await safe_respond(ctx, f":warning: {exc}")
            return

        vc = await self._ensure_voice_connection(ctx)
        if vc is None:
            return

        player = self.player_manager.get_or_create(ctx.guild_id)
        player.voice_client = vc

        position = await player.enqueue_and_play_if_idle(url, self.bot.loop)
        if position == 1 and player.is_playing():
            await safe_respond(ctx, f"再生します: {url}")
        else:
            await safe_respond(ctx, f"キューに追加しました (#{position}): {url}")

    @commands.slash_command(
        name="yt", description="YouTubeでキーワード検索を行い、結果の一番上を再生します。"
    )
    async def play_search(
        self, ctx: discord.ApplicationContext, query: str
    ) -> None:
        await ctx.defer()  # VC接続/検索は3秒を超えうるため先にdeferする

        vc = await self._ensure_voice_connection(ctx)
        if vc is None:
            return

        player = self.player_manager.get_or_create(ctx.guild_id)
        player.voice_client = vc

        try:
            track = await extract_track(query, is_search=True)
        except ExtractionError as exc:
            await safe_respond(ctx, f":warning: {exc}")
            return

        position = await player.enqueue_and_play_if_idle(
            track.webpage_url, self.bot.loop
        )
        if position == 1 and player.is_playing():
            await safe_respond(ctx, f"再生します: {track.title}")
        else:
            await safe_respond(ctx, f"キューに追加しました (#{position}): {track.title}")

    @commands.slash_command(name="stp", description="再生を停止し、ボイスチャンネルから退室します。")
    async def stop(self, ctx: discord.ApplicationContext) -> None:
        player = self.player_manager.get(ctx.guild_id)
        if player is None or player.voice_client is None:
            await safe_respond(ctx, "現在再生していません。")
            return

        player.stop()
        await player.voice_client.disconnect()
        self.player_manager.remove(ctx.guild_id)
        await safe_respond(ctx, "再生を停止しました。")

    @commands.slash_command(
        name="vol", description="音量を調整します(パーセント指定、デフォルトは100%)"
    )
    async def volume(self, ctx: discord.ApplicationContext, percent: float) -> None:
        player = self.player_manager.get(ctx.guild_id)
        if player is None:
            await safe_respond(ctx, "現在再生していません。")
            return
        from config import load_settings

        default_volume = load_settings().default_volume
        new_volume = player.set_volume(percent, default_volume)
        await safe_respond(ctx, f"音量を {percent}% に設定しました。(実際の係数: {new_volume:.2f})")

    @commands.slash_command(name="skp", description="現在の曲をスキップして次の曲を再生します。")
    async def skip(self, ctx: discord.ApplicationContext) -> None:
        player = self.player_manager.get(ctx.guild_id)
        if player is None or not player.is_playing():
            await safe_respond(ctx, "現在再生していません。")
            return
        player.skip()
        await safe_respond(ctx, "スキップしました。")

    @commands.slash_command(name="qe", description="現在のキューを表示します。")
    async def show_queue(self, ctx: discord.ApplicationContext) -> None:
        player = self.player_manager.get(ctx.guild_id)
        if player is None or not player.snapshot_queue():
            await safe_respond(ctx, "キューは空です。")
            return
        lines = [f"{i+1}. {q}" for i, q in enumerate(player.snapshot_queue())]
        await safe_respond(ctx, "現在のキュー:\n" + "\n".join(lines))

    @commands.slash_command(name="nop", description="現在再生中の曲の情報を表示します。")
    async def now_playing(self, ctx: discord.ApplicationContext) -> None:
        player = self.player_manager.get(ctx.guild_id)
        if player is None or player.now_playing is None:
            await safe_respond(ctx, "現在再生していません。")
            return
        track = player.now_playing
        await safe_respond(ctx, f"再生中: {track.title}\n{track.webpage_url}")

    @commands.slash_command(name="nsp", description="指定した番号の曲をキューから削除します。")
    async def remove_from_queue(
        self, ctx: discord.ApplicationContext, position: int
    ) -> None:
        player = self.player_manager.get(ctx.guild_id)
        if player is None:
            await safe_respond(ctx, "キューは空です。")
            return
        try:
            removed = player.remove_at(position)
        except IndexError as exc:
            await safe_respond(ctx, f":warning: {exc}")
            return
        await safe_respond(ctx, f"{position}番目のキュー ({removed}) を削除しました。")


def setup(bot: discord.Bot, player_manager: GuildPlayerManager) -> None:
    bot.add_cog(PlaybackCog(bot, player_manager))
