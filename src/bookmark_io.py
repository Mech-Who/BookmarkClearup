"""安全读取和写回 Chromium 书签 JSON 文件。"""

import json
import os
import shutil
import tempfile
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from src.entity import BookmarkFolder
from src.functional import dump_json_folder, parse_json_item


def load_bookmark_file(path: Path | str) -> tuple[dict, BookmarkFolder]:
    """读取文件，校验 bookmark_bar，并返回原始文档和内存树。"""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"bookmark file does not exist: {path}")
    try:
        with path.open("r", encoding="utf-8") as stream:
            document = json.load(stream)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in bookmark file: {path}") from exc
    except OSError as exc:
        raise OSError(f"cannot read bookmark file {path}: {exc}") from exc
    try:
        root = document["roots"]["bookmark_bar"]
    except (TypeError, KeyError) as exc:
        raise ValueError(f"bookmark file missing roots.bookmark_bar: {path}") from exc
    if not isinstance(root, dict):
        raise ValueError(f"roots.bookmark_bar must be an object: {path}")
    try:
        return document, parse_json_item(root)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid bookmark_bar in {path}: {exc}") from exc


def document_with_root(document: dict, root: BookmarkFolder) -> dict:
    """复制原始文档，仅替换 bookmark_bar，保留其他字段。"""
    result = deepcopy(document)
    result["roots"]["bookmark_bar"] = dump_json_folder(root)
    return result


def _backup_path(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    candidate = path.with_name(f"{path.name}.{stamp}.bak")
    suffix = 1
    while candidate.exists():
        candidate = path.with_name(f"{path.name}.{stamp}_{suffix}.bak")
        suffix += 1
    return candidate


def _atomic_write(path: Path, document: dict) -> None:
    """以同目录临时文件完成 flush、fsync、校验后原子替换。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=".bookmarkclearup-", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(document, stream, ensure_ascii=False, indent=4)
            stream.flush()
            os.fsync(stream.fileno())
        load_bookmark_file(temporary)
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def write_bookmark_file(path: Path | str, document: dict, *, output: bool = False, in_place: bool = False) -> tuple[Path, Path | None]:
    """安全写入新文件或显式原地覆盖，返回目标和备份路径。"""
    path = Path(path)
    if output and in_place:
        raise ValueError("output and in_place are mutually exclusive")
    if output and path.exists():
        raise FileExistsError(f"output file already exists: {path}")
    if not output and not in_place:
        raise ValueError("one of output or in_place is required")
    backup = None
    if in_place:
        if not path.is_file():
            raise FileNotFoundError(f"bookmark file does not exist: {path}")
        backup = _backup_path(path)
        shutil.copy2(path, backup)
    _atomic_write(path, document)
    return path, backup
