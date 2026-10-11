import json
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from zha_quirk_builder.model import efekta_sample
from zha_quirk_builder.profiles import (
    LATEST_PROFILE,
    CompatibilityProfile,
    _environment_python,
    ensure_profile,
    validate_with_profile,
)


def test_latest_profile_upgrades_without_version_pins(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("zha_quirk_builder.profiles.cache_root", lambda: tmp_path)
    monkeypatch.setattr("zha_quirk_builder.profiles._uv_binary", lambda: Path("/test/uv"))
    monkeypatch.setattr("zha_quirk_builder.profiles._package_index", lambda: None)
    run = Mock(return_value=subprocess.CompletedProcess([], 0, stdout="", stderr=""))
    monkeypatch.setattr("zha_quirk_builder.profiles.subprocess.run", run)

    python = ensure_profile(LATEST_PROFILE)

    install = run.call_args_list[-1].args[0]
    assert "--upgrade" in install
    assert "--prerelease=disallow" in install
    assert install[-3:] == ["zigpy", "zha", "zha-quirks"]
    assert not any("==" in arg for arg in install)
    assert python == _environment_python(tmp_path / "profiles" / LATEST_PROFILE.key)


def test_latest_profile_reuses_python_but_checks_for_updates(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("zha_quirk_builder.profiles.cache_root", lambda: tmp_path)
    monkeypatch.setattr("zha_quirk_builder.profiles._uv_binary", lambda: Path("/test/uv"))
    monkeypatch.setattr("zha_quirk_builder.profiles._package_index", lambda: None)
    environment = tmp_path / "profiles" / LATEST_PROFILE.key
    python = _environment_python(environment)
    python.parent.mkdir(parents=True)
    python.touch()
    run = Mock(return_value=subprocess.CompletedProcess([], 0, stdout="", stderr=""))
    monkeypatch.setattr("zha_quirk_builder.profiles.subprocess.run", run)

    ensure_profile(LATEST_PROFILE)
    ensure_profile(LATEST_PROFILE)

    assert run.call_count == 2
    assert all(call.args[0][1:3] == ["pip", "install"] for call in run.call_args_list)


def test_exact_profile_reuses_matching_cache(tmp_path: Path, monkeypatch) -> None:
    profile = CompatibilityProfile("Custom", "2.1.0", "2.2.0", "2.2.1")
    monkeypatch.setattr("zha_quirk_builder.profiles.cache_root", lambda: tmp_path)
    environment = tmp_path / "profiles" / profile.key
    python = _environment_python(environment)
    python.parent.mkdir(parents=True)
    python.touch()
    (environment / ".zha-quirk-builder-profile.json").write_text(
        json.dumps(
            {
                "zigpy": profile.zigpy,
                "zha": profile.zha,
                "zha-quirks": profile.zha_quirks,
            }
        )
    )
    run = Mock()
    monkeypatch.setattr("zha_quirk_builder.profiles.subprocess.run", run)

    assert ensure_profile(profile) == python
    run.assert_not_called()


def test_resolved_versions_are_reported_instead_of_profile_labels(monkeypatch) -> None:
    monkeypatch.setattr(
        "zha_quirk_builder.profiles.ensure_profile", lambda profile: Path("/test/python")
    )
    result = subprocess.CompletedProcess(
        [],
        0,
        stdout=json.dumps(
            {
                "python": "3.12.11",
                "zigpy": "2.1.4",
                "zha": "2.2.3",
                "zha-quirks": "2.2.4",
            }
        ),
        stderr="",
    )
    monkeypatch.setattr("zha_quirk_builder.profiles.subprocess.run", lambda *args, **kwargs: result)

    issues = validate_with_profile(efekta_sample(), LATEST_PROFILE)

    assert issues[-1].severity == "success"
    assert "zigpy 2.1.4, ZHA 2.2.3, zha-quirks 2.2.4 on Python 3.12.11" in issues[-1].message
    assert any(issue.severity == "warning" for issue in issues)


@pytest.mark.parametrize("output", ["", "not JSON", "{}", "[]"])
def test_missing_version_report_is_an_error(output: str, monkeypatch) -> None:
    monkeypatch.setattr(
        "zha_quirk_builder.profiles.ensure_profile", lambda profile: Path("/test/python")
    )
    result = subprocess.CompletedProcess([], 0, stdout=output, stderr="")
    monkeypatch.setattr("zha_quirk_builder.profiles.subprocess.run", lambda *args, **kwargs: result)

    issues = validate_with_profile(efekta_sample(), LATEST_PROFILE)

    assert issues[-1].severity == "error"
    assert "Could not read compatibility versions" in issues[-1].message


def test_latest_download_failure_is_not_presented_as_success(monkeypatch) -> None:
    def failed_install(profile):
        raise RuntimeError("Package index is unreachable")

    monkeypatch.setattr("zha_quirk_builder.profiles.ensure_profile", failed_install)

    issues = validate_with_profile(efekta_sample(), LATEST_PROFILE)

    assert issues[-1].severity == "error"
    assert "Package index is unreachable" in issues[-1].message
