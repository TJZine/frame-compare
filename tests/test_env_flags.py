import pytest

from src.frame_compare.env_flags import env_flag_enabled


@pytest.mark.parametrize("value", ["1", "true", " TRUE ", "Yes", "on", b"1"])
def test_env_flag_enabled_true_values(value: str | bytes) -> None:
    assert env_flag_enabled(value)


@pytest.mark.parametrize("value", [None, "", "   ", "0", "False", "off", "no", b"0"])
def test_env_flag_enabled_false_values(value: str | bytes | None) -> None:
    assert env_flag_enabled(value) is False


def test_env_flag_enabled_unknown_defaults_false() -> None:
    assert env_flag_enabled("maybe") is False
