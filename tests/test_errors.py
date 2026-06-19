import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from errors import safe_respond


def _make_ctx(is_done: bool) -> MagicMock:
    ctx = MagicMock()
    ctx.response.is_done.return_value = is_done
    ctx.respond = AsyncMock()
    ctx.followup.send = AsyncMock()
    return ctx


class TestSafeRespond:
    @pytest.mark.asyncio
    async def test_uses_respond_when_not_deferred(self):
        ctx = _make_ctx(is_done=False)
        await safe_respond(ctx, "hello")
        ctx.respond.assert_awaited_once_with("hello")
        ctx.followup.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_uses_followup_when_deferred(self):
        """ctx.defer()済みのinteractionにctx.respond()を呼ぶとNotFoundで失敗するため、
        followup.sendに自動的に切り替わることを確認する(今回の修正の本体)。"""
        ctx = _make_ctx(is_done=True)
        await safe_respond(ctx, "hello")
        ctx.followup.send.assert_awaited_once_with("hello")
        ctx.respond.assert_not_called()
