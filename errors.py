"""共通エラーハンドリング。discord.pyのコマンドエラーを一箇所で集約処理する。"""
from __future__ import annotations

import logging

import discord

logger = logging.getLogger(__name__)


async def safe_respond(ctx: discord.ApplicationContext, message: str) -> None:
    """ctx.respond / ctx.followup.send の例外をまとめてログに残す共通関数。
    旧実装では各コマンドで同じ except ブロックを繰り返していた。
    すでに defer() 済みの interaction には followup.send を使う必要があるため、
    ctx.response.is_done() で自動判別する。
    """
    try:
        if ctx.response.is_done():
            await ctx.followup.send(message)
        else:
            await ctx.respond(message)
    except discord.errors.NotFound:
        logger.error("応答に失敗しました(NotFound): interactionが失効しています。")
    except discord.errors.ApplicationCommandInvokeError as exc:
        logger.error("応答に失敗しました(InvokeError): %s", exc)


async def global_error_handler(
    ctx: discord.ApplicationContext, error: Exception
) -> None:
    """Bot全体のスラッシュコマンドエラーを集約するハンドラ。"""
    logger.exception(
        "コマンド '%s' の実行中にエラーが発生しました", ctx.command, exc_info=error
    )
    user_message = ":warning: コマンドの実行中にエラーが発生しました。"
    if isinstance(error, discord.errors.ApplicationCommandInvokeError):
        original = error.original
        user_message = f":warning: {original}"
    await safe_respond(ctx, user_message)
