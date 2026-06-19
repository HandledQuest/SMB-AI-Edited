import pytest

from music.source import InvalidURLError, validate_url


class TestValidateURL:
    @pytest.mark.parametrize(
        "url",
        [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "http://example.com/audio.mp3",
            "https://soundcloud.com/some/track",
        ],
    )
    def test_valid_public_urls_pass(self, url):
        validate_url(url)  # 例外が出ないことを確認

    @pytest.mark.parametrize(
        "url",
        [
            "ftp://example.com/file.mp3",
            "file:///etc/passwd",
            "not-a-url",
            "javascript:alert(1)",
        ],
    )
    def test_invalid_scheme_rejected(self, url):
        with pytest.raises(InvalidURLError):
            validate_url(url)

    @pytest.mark.parametrize(
        "url",
        [
            "http://localhost/admin",
            "http://127.0.0.1:8080/internal",
            "http://10.0.0.5/secret",
            "http://192.168.1.1/router",
            "http://169.254.169.254/latest/meta-data/",  # クラウドのメタデータエンドポイント
            "http://172.16.0.1/internal",
        ],
    )
    def test_private_and_local_hosts_rejected(self, url):
        """SSRF対策: 内部ネットワーク/クラウドメタデータへのアクセスを防止できているか。"""
        with pytest.raises(InvalidURLError):
            validate_url(url)
