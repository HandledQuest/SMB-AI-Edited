from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from update import ReleaseInfo, check_for_update, is_newer


class TestIsNewer:
    def test_newer_patch_version(self):
        assert is_newer("v2.0.1", current="2.0.0") is True

    def test_newer_minor_version(self):
        assert is_newer("v2.1.0", current="2.0.0") is True

    def test_same_version_is_not_newer(self):
        assert is_newer("v2.0.0", current="2.0.0") is False

    def test_older_version_is_not_newer(self):
        assert is_newer("v1.9.0", current="2.0.0") is False

    def test_handles_missing_v_prefix(self):
        assert is_newer("2.5.0", current="2.0.0") is True

    def test_malformed_tag_does_not_raise(self):
        # 例外を投げずFalseを返すこと(更新チェックの失敗で起動が止まらないように)
        assert is_newer("not-a-version", current="2.0.0") is False


class _FakeResponse:
    def __init__(self, status: int, json_data: dict | None = None):
        self.status = status
        self._json_data = json_data or {}

    async def json(self):
        return self._json_data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class _FakeSession:
    def __init__(self, response: _FakeResponse):
        self._response = response

    def get(self, *args, **kwargs):
        return self._response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class TestCheckForUpdate:
    @pytest.mark.asyncio
    async def test_returns_release_info_on_success(self):
        fake_response = _FakeResponse(
            status=200,
            json_data={
                "tag_name": "v2.1.0",
                "html_url": "https://github.com/HandledQuest/SMB-AI-Edited/releases/tag/v2.1.0",
                "published_at": "2026-06-01T00:00:00Z",
            },
        )
        with patch(
            "aiohttp.ClientSession", return_value=_FakeSession(fake_response)
        ):
            result = await check_for_update(
                "https://api.github.com/repos/HandledQuest/SMB-AI-Edited"
            )

        assert result == ReleaseInfo(
            tag_name="v2.1.0",
            html_url="https://github.com/HandledQuest/SMB-AI-Edited/releases/tag/v2.1.0",
            published_at="2026-06-01T00:00:00Z",
        )

    @pytest.mark.asyncio
    async def test_returns_none_when_no_releases_yet(self):
        """リリースをまだ作成していないリポジトリ(404)でも例外にならないことを確認。"""
        fake_response = _FakeResponse(status=404)
        with patch(
            "aiohttp.ClientSession", return_value=_FakeSession(fake_response)
        ):
            result = await check_for_update(
                "https://api.github.com/repos/HandledQuest/SMB-AI-Edited"
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_rate_limit(self):
        fake_response = _FakeResponse(status=403)
        with patch(
            "aiohttp.ClientSession", return_value=_FakeSession(fake_response)
        ):
            result = await check_for_update(
                "https://api.github.com/repos/HandledQuest/SMB-AI-Edited"
            )
        assert result is None
