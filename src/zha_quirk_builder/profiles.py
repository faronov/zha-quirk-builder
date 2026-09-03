from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit

from zha_quirk_builder.generator import generate_quirk
from zha_quirk_builder.model import QuirkProject
from zha_quirk_builder.validator import ValidationIssue, validate_import, validate_project


@dataclass(frozen=True, slots=True)
class CompatibilityProfile:
    name: str
    zigpy: str
    zha: str
    zha_quirks: str
    bundled: bool = False

    @property
    def label(self) -> str:
        if self.bundled:
            return f"{self.name} · versions packaged with the app"
        return (
            f"{self.name} · zigpy {self.zigpy} / ZHA {self.zha} / "
            f"quirks {self.zha_quirks}"
        )

    @property
    def key(self) -> str:
        versions = f"{self.zigpy}:{self.zha}:{self.zha_quirks}"
        return sha256(versions.encode()).hexdigest()[:12]


BUNDLED_PROFILE = CompatibilityProfile("Bundled", "", "", "", bundled=True)
LATEST_PROFILE = CompatibilityProfile("Latest stable", "2.1.0", "2.2.1", "2.2.1")


def cache_root() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "ZHA Quirk Builder"
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ZHA Quirk Builder" / "Cache"
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "zha-quirk-builder"


def _uv_binary() -> Path:
    if getattr(sys, "frozen", False):
        name = "uv.exe" if sys.platform == "win32" else "uv"
        bundled = Path(sys._MEIPASS) / name  # type: ignore[attr-defined]
        if bundled.is_file():
            return bundled
    from uv import find_uv_bin

    return Path(find_uv_bin())


def _environment_python(environment: Path) -> Path:
    if sys.platform == "win32":
        return environment / "Scripts" / "python.exe"
    return environment / "bin" / "python"


def _package_index() -> str | None:
    index = os.environ.get("UV_DEFAULT_INDEX") or os.environ.get("PIP_INDEX_URL")
    if not index and not getattr(sys, "frozen", False):
        configured = subprocess.run(
            [sys.executable, "-m", "pip", "config", "debug"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        for line in configured.stdout.splitlines():
            if "global.index-url:" in line:
                index = line.split("global.index-url:", 1)[1].strip()
                break
    if not index:
        return None
    parsed = urlsplit(index)
    if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password:
        return None
    return index


def ensure_profile(profile: CompatibilityProfile, timeout: int = 600) -> Path:
    if profile.bundled:
        return Path(sys.executable)

    environment = cache_root() / "profiles" / profile.key
    python = _environment_python(environment)
    marker = environment / ".zha-quirk-builder-profile.json"
    expected = {
        "zigpy": profile.zigpy,
        "zha": profile.zha,
        "zha-quirks": profile.zha_quirks,
    }
    if python.is_file() and marker.is_file():
        try:
            if json.loads(marker.read_text(encoding="utf-8")) == expected:
                return python
        except (OSError, json.JSONDecodeError):
            pass

    environment.parent.mkdir(parents=True, exist_ok=True)
    uv_binary = str(_uv_binary())
    create = subprocess.run(
        [uv_binary, "venv", "--clear", "--python", "3.12", str(environment)],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if create.returncode:
        detail = create.stderr.strip() or create.stdout.strip()
        raise RuntimeError(f"Could not create compatibility environment: {detail}")

    install_command = [
        uv_binary,
        "pip",
        "install",
        "--python",
        str(python),
    ]
    if package_index := _package_index():
        install_command.extend(("--default-index", package_index))
    install_command.extend(
        (
            f"zigpy=={profile.zigpy}",
            f"zha=={profile.zha}",
            f"zha-quirks=={profile.zha_quirks}",
        )
    )
    install = subprocess.run(
        install_command,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if install.returncode:
        detail = install.stderr.strip() or install.stdout.strip()
        raise RuntimeError(f"Could not install compatibility profile: {detail}")
    marker.write_text(json.dumps(expected, indent=2), encoding="utf-8")
    return python


def validate_with_profile(
    project: QuirkProject, profile: CompatibilityProfile, timeout: int = 30
) -> list[ValidationIssue]:
    if profile.bundled:
        return validate_import(project, timeout=timeout)

    issues = validate_project(project)
    if any(issue.severity == "error" for issue in issues):
        return issues

    try:
        python = ensure_profile(profile)
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        issues.append(ValidationIssue("error", str(error)))
        return issues

    with tempfile.TemporaryDirectory(prefix="zha-quirk-builder-") as directory:
        quirk = Path(directory) / "generated_quirk.py"
        quirk.write_text(generate_quirk(project), encoding="utf-8")
        try:
            result = subprocess.run(
                [str(python), "-I", str(quirk)],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            issues.append(
                ValidationIssue("error", f"Upstream import exceeded the {timeout} second timeout.")
            )
            return issues

    if result.returncode:
        detail = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "unknown error"
        issues.append(ValidationIssue("error", f"Upstream import failed: {detail}"))
    else:
        issues.append(
            ValidationIssue(
                "success",
                f"Imported with zigpy {profile.zigpy}, ZHA {profile.zha}, "
                f"zha-quirks {profile.zha_quirks}.",
            )
        )
    return issues
