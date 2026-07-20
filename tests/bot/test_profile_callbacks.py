"""Tests for bot.profile_callbacks."""

from unittest.mock import MagicMock

from bot.profile_callbacks import (
    PROFILE_NAMES_KEY,
    cache_profile_names,
    resolve_profile_from_callback,
)


def _ctx(profile_names=None):
    ctx = MagicMock()
    ctx.user_data = {PROFILE_NAMES_KEY: profile_names} if profile_names is not None else {}
    return ctx


class TestCacheProfileNames:
    def test_caches_list(self):
        ctx = _ctx()
        cache_profile_names(ctx, ["1M", "2M", "5M"])
        assert ctx.user_data[PROFILE_NAMES_KEY] == ["1M", "2M", "5M"]

    def test_copies_to_avoid_mutation(self):
        ctx = _ctx()
        original = ["1M", "2M"]
        cache_profile_names(ctx, original)
        original.append("HACKED")
        assert ctx.user_data[PROFILE_NAMES_KEY] == ["1M", "2M"]

    def test_empty_list(self):
        ctx = _ctx()
        cache_profile_names(ctx, [])
        assert ctx.user_data[PROFILE_NAMES_KEY] == []


class TestResolveProfileFromCallback:
    def test_valid_index(self):
        ctx = _ctx(["1M", "2M", "5M"])
        result = resolve_profile_from_callback(ctx, "card_profile_0", "card_profile_")
        assert result == "1M"

    def test_valid_last_index(self):
        ctx = _ctx(["1M", "2M", "5M"])
        result = resolve_profile_from_callback(ctx, "card_profile_2", "card_profile_")
        assert result == "5M"

    def test_negative_index_returns_none(self):
        ctx = _ctx(["1M", "2M"])
        result = resolve_profile_from_callback(ctx, "card_profile_-1", "card_profile_")
        assert result is None

    def test_out_of_range_returns_none(self):
        ctx = _ctx(["1M", "2M"])
        result = resolve_profile_from_callback(ctx, "card_profile_99", "card_profile_")
        assert result is None

    def test_non_numeric_suffix_returns_none(self):
        ctx = _ctx(["1M", "2M"])
        result = resolve_profile_from_callback(ctx, "card_profile_abc", "card_profile_")
        assert result is None

    def test_no_cached_profiles_returns_none(self):
        ctx = _ctx()
        result = resolve_profile_from_callback(ctx, "card_profile_0", "card_profile_")
        assert result is None

    def test_different_prefix(self):
        ctx = _ctx(["A", "B"])
        result = resolve_profile_from_callback(ctx, "edit_profile_1", "edit_profile_")
        assert result == "B"
