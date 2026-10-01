from persistence import now_et


def test_eastern_timezone_name():
    assert getattr(now_et().tzinfo, "key", None) == "America/New_York"
