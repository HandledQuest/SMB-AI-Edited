"""歌詞取得コマンド。lyricsgeniusはブロッキングI/Oのため非同期executorでラップする。"""
import logging
from typing import Optional

import discord
import lyricsgenius
from discord.ext import commands

from errors import safe_respond
from music.manager import GuildPlayerManager

logger = logging.getLogger(__name__)

MAX_DISCORD_MESSAGE_LENGTH = 2000
LYRICS_TRUNCATE_NOTICE = "\n\n…(文字数制限のため省略されました)"


class LyricsCog(commands.Cog):
    def __init__(
        self,
        bot: discord.Bot,
        player_manager: GuildPlayerManager,
        genius_token: str,
    ) -> None:
        self.bot = bot
        self.player_manager = player_manager
        self._genius_token = genius_token
        self._genius_client: Optional[lyricsgenius.Genius] = None

    def _get_client(self) -> Optional[lyricsgenius.Genius]:
        if not self._genius_token:
            return None
        if self._genius_client is None:
            self._genius_client = lyricsgenius.Genius(
                self._genius_token,
                verbose=False,
                remove_section_headers=False,
                timeout=10,
            )
        return self._genius_client

    def _search_lyrics_sync(self, title: str) -> Optional[str]:
        client = self._get_client()
        if client is None:
            return None
        song = client.search_song(title)
        if song is None:
            return None
        return song.lyrics

    @commands.slash_command(
        name="ly", description="現在再生中、または指定した曲の歌詞を表示します。"
    )
    async def lyrics(
        self, ctx: discord.ApplicationContext, title: Optional[str] = None
    ) -> None:
        if not self._genius_token:
            await safe_respond(
                ctx,
                ":warning: 歌詞検索機能は設定されていません"
                "(GENIUS_TOKEN が未設定です)。",
            )
            return

        search_title = title
        if search_title is None:
            player = self.player_manager.get(ctx.guild_id)
            if player is None or player.now_playing is None:
                await safe_respond(
                    ctx, "現在再生中の曲がありません。タイトルを指定してください。"
                )
                return
            search_title = player.now_playing.title

        await ctx.defer()

        loop = self.bot.loop
        try:
            lyrics_text = await loop.run_in_executor(
                None, self._search_lyrics_sync, search_title
            )
        except Exception as exc:  # Genius API障害、ネットワークエラー等
            logger.exception("歌詞検索中にエラーが発生しました: %s", search_title)
            await ctx.followup.send(f":warning: 歌詞検索に失敗しました: {exc}")
            return

        if lyrics_text is None:
            await ctx.followup.send(f"「{search_title}」の歌詞が見つかりませんでした。")
            return

        if len(lyrics_text) > MAX_DISCORD_MESSAGE_LENGTH:
            cutoff = MAX_DISCORD_MESSAGE_LENGTH - len(LYRICS_TRUNCATE_NOTICE)
            lyrics_text = lyrics_text[:cutoff] + LYRICS_TRUNCATE_NOTICE

        await ctx.followup.send(lyrics_text)


def setup(
    bot: discord.Bot, player_manager: GuildPlayerManager, genius_token: str
) -> None:
    bot.add_cog(LyricsCog(bot, player_manager, genius_token))
