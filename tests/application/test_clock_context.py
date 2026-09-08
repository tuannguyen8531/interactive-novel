import pytest

from src.application.contracts.clock import StoryTimeContext


@pytest.mark.parametrize(
    ("minutes", "day", "time_24h", "period"),
    [
        (0, 1, "00:00", "night"),
        (359, 1, "05:59", "night"),
        (360, 1, "06:00", "morning"),
        (720, 1, "12:00", "afternoon"),
        (930, 1, "15:30", "afternoon"),
        (1080, 1, "18:00", "evening"),
        (1320, 1, "22:00", "night"),
        (1439, 1, "23:59", "night"),
        (1440, 2, "00:00", "night"),
        (1530, 2, "01:30", "night"),
    ],
)
def test_clock_context_uses_elapsed_minutes_not_hhmm(minutes: int, day: int, time_24h: str, period: str) -> None:
    context = StoryTimeContext.from_minutes(minutes)
    assert context.model_dump() == {"world_time": minutes, "day": day, "time_24h": time_24h, "period": period}
