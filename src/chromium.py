"""Chromium browser paths and profile discovery."""
import os
import sys
from pathlib import Path

_PLATFORM_ROOTS = {
    "win": {"chrome": Path("Google") / "Chrome" / "User Data", "edge": Path("Microsoft") / "Edge" / "User Data"},
    "darwin": {"chrome": Path("Library/Application Support/Google/Chrome"), "edge": Path("Library/Application Support/Microsoft Edge")},
    "linux": {"chrome": Path("google-chrome"), "edge": Path("microsoft-edge")},
}


def _platform_key(platform: str) -> str:
    """Normalize platform names to the path mapping keys."""
    if platform.startswith("win"):
        return "win"
    if platform == "darwin":
        return "darwin"
    if platform.startswith("linux"):
        return "linux"
    raise ValueError(f"unsupported platform: {platform}")


def browser_user_data_dir(browser: str, *, platform: str | None = None, environ: dict | None = None, home: Path | str | None = None) -> Path:
    """Return Chrome or Edge User Data path on Windows, macOS, or Linux."""
    browser = browser.lower()
    variables = os.environ if environ is None else environ
    if browser not in ("chrome", "edge"):
        raise ValueError(f"unsupported Chromium browser: {browser}")
    key = _platform_key(platform or sys.platform)
    home_path = Path(home) if home is not None else Path(variables.get("HOME", Path.home()))
    if key == "win":
        local = variables.get("LOCALAPPDATA")
        if not local:
            raise EnvironmentError("LOCALAPPDATA is required to locate Chromium profiles")
        return Path(local) / _PLATFORM_ROOTS[key][browser]
    if key == "darwin":
        return home_path / _PLATFORM_ROOTS[key][browser]
    config = Path(variables.get("XDG_CONFIG_HOME", home_path / ".config"))
    return config / _PLATFORM_ROOTS[key][browser]


def discover_profiles(browser: str, *, platform: str | None = None, environ: dict | None = None, home: Path | str | None = None) -> list[str]:
    """List profile directories under User Data."""
    root = browser_user_data_dir(browser, platform=platform, environ=environ, home=home)
    if not root.is_dir():
        raise FileNotFoundError(f"Chromium User Data directory does not exist: {root}")
    return sorted(path.name for path in root.iterdir() if path.is_dir() and (path.name == "Default" or path.name.startswith("Profile ") or (path / "Preferences").exists()))


def profile_bookmarks_path(browser: str, profile: str, *, platform: str | None = None, environ: dict | None = None, home: Path | str | None = None) -> Path:
    """Return a profile's Bookmarks file path."""
    if not profile or Path(profile).name != profile:
        raise ValueError(f"invalid Chromium profile name: {profile}")
    path = browser_user_data_dir(browser, platform=platform, environ=environ, home=home) / profile / "Bookmarks"
    if not path.is_file():
        raise FileNotFoundError(f"Chromium profile Bookmarks does not exist: {path}")
    return path