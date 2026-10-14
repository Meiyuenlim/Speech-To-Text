from __future__ import annotations

import os
import shutil
from pathlib import Path


def resolve_executable(name: str, environment_variable: str | None = None) -> str | None:
    """Resolve local tools even when a Windows package updated PATH after the shell started."""
    configured = os.getenv(environment_variable) if environment_variable else None
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.is_dir():
            candidate = candidate / (f"{name}.exe" if os.name == "nt" else name)
        if candidate.is_file():
            return str(candidate)

    found = shutil.which(name)
    if found:
        return found

    if os.name != "nt":
        return None

    local_app_data = os.getenv("LOCALAPPDATA")
    roots = [
        Path("C:/ffmpeg/bin"),
        Path("C:/Program Files/ffmpeg/bin"),
    ]
    if local_app_data:
        roots.insert(0, Path(local_app_data) / "Microsoft" / "WinGet" / "Packages")
    executable_name = f"{name}.exe"
    for root in roots:
        if not root.exists():
            continue
        matches = root.glob(f"**/{executable_name}")
        for match in matches:
            if match.is_file():
                return str(match)
    return None
