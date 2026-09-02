import shutil
import uuid
from pathlib import Path

import pytest


@pytest.fixture
def repo_temp_dir():
    """Provide an isolated temporary directory inside the repository."""
    path = Path("test") / ".tmp" / uuid.uuid4().hex
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
