from __future__ import annotations

import logging
from pathlib import Path

import pytest

from fram_serving.config import FRAMConfig


def test_storage_root_can_be_isolated_from_the_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    storage_root = tmp_path / "runtime-storage"
    monkeypatch.setenv("FRAM_STORAGE_ROOT", str(storage_root))

    config = FRAMConfig.from_env()

    assert config.STORAGE_ROOT == storage_root


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on"])
def test_dev_profile_accepts_only_explicit_true_values(
    value: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FRAM_DEV_PROFILE", value)
    monkeypatch.delenv("FRAM_FRACTAL_ENABLED", raising=False)

    assert FRAMConfig.from_env().fractal_enabled is True


@pytest.mark.parametrize("value", ["", "0", "false", "FALSE", "no", "off"])
def test_dev_profile_false_values_stay_disabled(
    value: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FRAM_DEV_PROFILE", value)
    monkeypatch.delenv("FRAM_FRACTAL_ENABLED", raising=False)

    assert FRAMConfig.from_env().fractal_enabled is False


def test_invalid_dev_profile_value_fails_closed(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("FRAM_DEV_PROFILE", "sometimes")
    monkeypatch.delenv("FRAM_FRACTAL_ENABLED", raising=False)

    with caplog.at_level(logging.WARNING):
        config = FRAMConfig.from_env()

    assert config.fractal_enabled is False
    assert "treating the profile as disabled" in caplog.text


def test_explicit_fractal_setting_overrides_dev_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FRAM_DEV_PROFILE", "1")
    monkeypatch.setenv("FRAM_FRACTAL_ENABLED", "0")

    assert FRAMConfig.from_env().fractal_enabled is False
