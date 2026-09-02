from pathlib import Path
import pytest
from src.chromium import browser_user_data_dir

def test_platform_paths_and_injected_environment(repo_temp_dir):
    home = repo_temp_dir / "home"
    assert browser_user_data_dir("chrome", platform="win32", environ={"LOCALAPPDATA": "C:/Local"}) == Path("C:/Local/Google/Chrome/User Data")
    assert browser_user_data_dir("edge", platform="darwin", home=home, environ={}) == home / "Library/Application Support/Microsoft Edge"
    assert browser_user_data_dir("chrome", platform="linux", home=home, environ={}) == home / ".config/google-chrome"
    assert browser_user_data_dir("edge", platform="linux", home=home, environ={"XDG_CONFIG_HOME": "/xdg"}) == Path("/xdg/microsoft-edge")
    with pytest.raises(ValueError):
        browser_user_data_dir("firefox", platform="linux", home=home, environ={})
    with pytest.raises(ValueError):
        browser_user_data_dir("chrome", platform="freebsd", home=home, environ={})