from datetime import datetime, timezone

import pytest


def test_season_to_string_uses_previous_and_end_year():
    from season_utils import season_to_string

    assert season_to_string(2026) == "2025-2026"
    assert season_to_string(2000) == "1999-2000"


def test_season_from_string_accepts_range_or_year():
    from season_utils import season_from_string

    assert season_from_string("2025-2026") == 2026
    assert season_from_string("2026") == 2026
    assert season_from_string(" 2025-2026 ") == 2026


def test_normalize_season_accepts_int_or_string():
    from season_utils import normalize_season

    assert normalize_season(2026) == "2025-2026"
    assert normalize_season("2026") == "2025-2026"
    assert normalize_season("2025-2026") == "2025-2026"


def test_current_fie_season_uses_july_boundary(monkeypatch):
    import season_utils

    class JuneDateTime:
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 6, 30, tzinfo=timezone.utc)

    class JulyDateTime:
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 7, 1, tzinfo=timezone.utc)

    monkeypatch.setattr(season_utils, "datetime", JuneDateTime)
    assert season_utils.current_fie_season() == 2025

    monkeypatch.setattr(season_utils, "datetime", JulyDateTime)
    assert season_utils.current_fie_season() == 2026


@pytest.mark.parametrize(
    "raw",
    ["", "abc", "2025/2026", "2026-2025", "2025-26", "2025-2026-2027"],
)
def test_season_from_string_rejects_invalid_values(raw):
    from season_utils import season_from_string

    with pytest.raises(ValueError):
        season_from_string(raw)


def test_normalize_season_rejects_unsupported_types():
    from season_utils import normalize_season

    with pytest.raises(TypeError):
        normalize_season(None)
