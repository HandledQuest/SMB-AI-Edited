"""SimpleMusicBot エントリポイント。"""
from __future__ import annotations

import logging
import sys

import discord

from cogs import lyrics as lyrics_cog
from cogs import playback as playback_cog
from config import ensure_config_dir, load_settings, write_example_env
from errors import global_error_handler
from logging_setup import setup_logging
from music.manager import GuildPlayerManager
from update import check_for_update, is_newer

logger = logging.getLogger(__name__)


def build_bot(settings) -> discord.Bot:
    intents = discord.Intents.default()
    intents.voice_states = True  # ボイスチャンネルの入退室検知に必要
    intents.members = False  # 音楽Botには不要な特権インテントは要求しない

    bot = discord.Bot(intents=intents)
    player_manager = GuildPlayerManager(default_volume=settings.default_volume)

    playback_cog.setup(bot, player_manager)
    lyrics_cog.setup(bot, player_manager, settings.genius_token)

    @bot.event
    async def on_ready() -> None:
        logger.info("ログインしました: %s (ID: %s)", bot.user, bot.user.id)
        await bot.change_presence(activity=discord.Game(name=settings.status))

        if settings.update_check:
            release = await check_for_update(settings.repository_url)
            if release and is_newer(release.tag_name):
                logger.warning(
                    "新しいバージョン %s が利用可能です。"
                    "リリースページを確認してください: %s",
                    release.tag_name,
                    release.html_url,
                )

    @bot.event
    async def on_application_command_error(
        ctx: discord.ApplicationContext, error: Exception
    ) -> None:
        await global_error_handler(ctx, error)

    @bot.event
    async def on_voice_state_update(
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        # Bot自身が一人だけVCに残された場合は再生を止めて退室する
        if member.bot:
            return
        voice_client = member.guild.voice_client
        if voice_client is None or before.channel is None:
            return
        if voice_client.channel != before.channel:
            return
        remaining_humans = [m for m in before.channel.members if not m.bot]
        if not remaining_humans:
            player = player_manager.get(member.guild.id)
            if player:
                player.stop()
            await voice_client.disconnect()
            player_manager.remove(member.guild.id)
            logger.info(
                "ギルド %s: VCに人がいなくなったため自動退室しました。", member.guild.id
            )

    return bot


def main() -> None:
    ensure_config_dir()
    write_example_env()

    settings = load_settings()
    setup_logging(settings.log_level)

    if not settings.is_token_configured:
        logger.error(
            "DISCORD_BOT_TOKEN が設定されていません。"
            ".env ファイルを作成し、トークンを設定してください"
            "(.env.example を参考にしてください)。"
        )
        sys.exit(1)

    bot = build_bot(settings)
    bot.run(settings.discord_bot_token)


if __name__ == "__main__":
    main()
