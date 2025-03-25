import os
import platform
from enum import StrEnum

base_path = None
match platform.system():
    case "Linux":
        raise NotImplementedError("OS not support!")
    case "Darwin":
        raise NotImplementedError("OS not support!")
    case "Windows":
        base_path = os.environ["LOCALAPPDATA"]


class DefaultBookmarkPath(StrEnum):
    CHROME = rf"{base_path}\Google\Chrome\User Data\Default\Bookmarks"
    EDGE = rf"{base_path}\Microsoft\Edge\User Data\Default\Bookmarks"
