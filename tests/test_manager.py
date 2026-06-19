import pytest

from music.manager import GuildPlayer, GuildPlayerManager


class TestGuildPlayerQueue:
    def test_enqueue_returns_position(self):
        player = GuildPlayer(guild_id=1)
        assert player.enqueue("a") == 1
        assert player.enqueue("b") == 2
        assert player.enqueue("c") == 3

    def test_snapshot_queue_reflects_order(self):
        player = GuildPlayer(guild_id=1)
        player.enqueue("a")
        player.enqueue("b")
        assert player.snapshot_queue() == ["a", "b"]

    def test_remove_at_valid_position(self):
        player = GuildPlayer(guild_id=1)
        player.enqueue("a")
        player.enqueue("b")
        player.enqueue("c")
        removed = player.remove_at(2)
        assert removed == "b"
        assert player.snapshot_queue() == ["a", "c"]

    @pytest.mark.parametrize("position", [0, -1, 99])
    def test_remove_at_out_of_range_raises(self, position):
        player = GuildPlayer(guild_id=1)
        player.enqueue("a")
        with pytest.raises(IndexError):
            player.remove_at(position)

    def test_stop_clears_queue_and_now_playing(self):
        player = GuildPlayer(guild_id=1)
        player.enqueue("a")
        player.now_playing = object()
        player.stop()
        assert player.snapshot_queue() == []
        assert player.now_playing is None


class TestGuildPlayerVolume:
    def test_set_volume_applies_default_volume_scaling(self):
        player = GuildPlayer(guild_id=1)
        # 100% * default(0.2) = 0.2
        result = player.set_volume(100, default_volume=0.2)
        assert result == pytest.approx(0.2)

    def test_set_volume_never_negative(self):
        player = GuildPlayer(guild_id=1)
        result = player.set_volume(-50, default_volume=0.2)
        assert result == 0.0


class TestGuildPlayerManagerIsolation:
    def test_get_or_create_returns_distinct_players_per_guild(self):
        manager = GuildPlayerManager(default_volume=0.2)
        player_a = manager.get_or_create(111)
        player_b = manager.get_or_create(222)
        assert player_a is not player_b

    def test_state_does_not_leak_between_guilds(self):
        """旧実装最大の問題: グローバルキュー共有によるマルチサーバー間の混在を防止できているか。"""
        manager = GuildPlayerManager(default_volume=0.2)
        player_a = manager.get_or_create(111)
        player_b = manager.get_or_create(222)

        player_a.enqueue("guildA-song1")
        player_a.enqueue("guildA-song2")

        assert player_a.snapshot_queue() == ["guildA-song1", "guildA-song2"]
        assert player_b.snapshot_queue() == []

    def test_get_or_create_is_idempotent(self):
        manager = GuildPlayerManager(default_volume=0.2)
        first = manager.get_or_create(111)
        first.enqueue("song")
        second = manager.get_or_create(111)
        assert second.snapshot_queue() == ["song"]

    def test_remove_player(self):
        manager = GuildPlayerManager(default_volume=0.2)
        manager.get_or_create(111)
        manager.remove(111)
        assert manager.get(111) is None
