"""Shared atomic file writing primitives."""
from __future__ import annotations

import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


def backup_path(path: Path) -> Path:
    """Return a unique timestamped backup path beside path."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = path.with_name(f"{path.name}.{stamp}_bookmark_backup.bak")
    index = 0
    while True:
        if index:
            candidate = path.with_name(f"{path.name}.{stamp}_bookmark_backup_{index}.bak")
        try:
            os.link(path, candidate)
            return candidate
        except FileExistsError:
            index += 1


def atomic_write(
    path: Path | str,
    data: str,
    validator: Callable[[Path], None],
    *,
    output: bool,
    in_place: bool,
    confirm: bool = False,
) -> Path | None:
    """Write atomically, validating a same-directory temp before link/replace."""
    # 1. Validate target and create a same-directory temporary file.
    target = Path(path)
    if output == in_place:
        raise ValueError("exactly one of output or in_place is required")
    if output and target.exists():
        raise FileExistsError(f"output file already exists: {target}")
    if in_place and not target.is_file():
        raise FileNotFoundError(f"bookmark file does not exist: {target}")
    if in_place and not confirm:
        raise PermissionError("explicit confirmation required")
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".bookmarkclearup-", suffix=".tmp", dir=target.parent)
    temporary = Path(name)
    backup = None
    try:
        # 2. Write and fsync the temporary file.
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        # 3. Validate the temporary file.
        validator(temporary)
        # 4. Create the backup and atomically commit the final file.
        if in_place:
            backup = backup_path(target)
            os.replace(temporary, target)
        else:
            os.link(temporary, target)
            temporary.unlink()
        return backup
    except Exception:
        try:
            temporary.unlink(missing_ok=True)
        except OSError as cleanup_error:
            logger.warning("cannot clean temporary file %s: %s", temporary, cleanup_error)
        raise
