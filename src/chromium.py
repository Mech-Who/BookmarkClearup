"""Chromium browser paths and profile discovery."""

import os
from pathlib import Path

_BROWSERS = {"chrome": Path("Google") / "Chrome" / "User Data", "edge": Path("Microsoft") / "Edge" / "User Data"}


def browser_user_data_dir(browser: str, *, environ: dict | None = None) -> Path:
    """Return the Windows User Data directory for Chrome or Edge."""
    browser = browser.lower()
    if browser not in _BROWSERS:
        raise ValueError(f"unsupported Chromium browser: {browser}")
    variables = os.environ if environ is None else environ
    local_app_data = variables.get("LOCALAPPDATA")
    if not local_app_data:
        raise EnvironmentError("LOCALAPPDATA is required to locate Chromium profiles")
    return Path(local_app_data) / _BROWSERS[browser]


def discover_profiles(browser: str, *, environ: dict | None = None) -> list[str]:
    """List profile directories under User Data."""
    root = browser_user_data_dir(browser, environ=environ)
    if not root.is_dir():
        raise FileNotFoundError(f"Chromium User Data directory does not exist: {root}")
    return sorted(path.name for path in root.iterdir() if path.is_dir() and (path.name == "Default" or path.name.startswith("Profile ") or (path / "Preferences").exists()))


def profile_bookmarks_path(browser: str, profile: str, *, environ: dict | None = None) -> Path:
    """Return a profile's Bookmarks file path."""
    if not profile or Path(profile).name != profile:
        raise ValueError(f"invalid Chromium profile name: {profile}")
    path = browser_user_data_dir(browser, environ=environ) / profile / "Bookmarks"
    if not path.is_file():
        raise FileNotFoundError(f"Chromium profile Bookmarks does not exist: {path}")
    return path
