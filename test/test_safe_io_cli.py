import json
import shutil
import uuid
from pathlib import Path

import pytest

from src.bookmark_io import load_bookmark_file, write_bookmark_file
from src.cli import main
from src.functional import merge, parse_json_item, visit


@pytest.fixture
def repo_temp_dir():
    path = Path("test") / ".tmp" / uuid.uuid4().hex
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _document(*urls):
    return {
        "checksum": "keep-me",
        "roots": {
            "bookmark_bar": {
                "children": [
                    {"name": url, "type": "url", "url": url, "id": str(i + 2), "date_added": "1", "date_last_used": "0"}
                    for i, url in enumerate(urls)
                ],
                "name": "Bookmarks",
                "type": "folder",
                "id": "1",
                "date_added": "1",
                "date_last_used": "0",
                "date_modified": "1",
            },
            "other": {"name": "Other", "type": "folder", "children": []},
        },
    }


def _write(path, document):
    path.write_text(json.dumps(document), encoding="utf-8")


def test_load_rejects_invalid_json_and_missing_bookmark_bar(repo_temp_dir):
    invalid = repo_temp_dir / "invalid.json"
    invalid.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid JSON"):
        load_bookmark_file(invalid)

    missing = repo_temp_dir / "missing.json"
    _write(missing, {"roots": {}})
    with pytest.raises(ValueError, match="bookmark_bar"):
        load_bookmark_file(missing)


def test_dry_run_cli_does_not_write_files(repo_temp_dir, capsys):
    base = repo_temp_dir / "base.json"
    source = repo_temp_dir / "source.json"
    _write(base, _document("https://base.example"))
    _write(source, _document("https://new.example"))
    before = base.read_bytes()

    assert main(["--base", str(base), "--source", str(source)]) == 0

    assert base.read_bytes() == before
    output = capsys.readouterr().out
    assert "base=1" in output
    assert "new=1" in output


def test_output_creates_new_file_and_refuses_existing_target(repo_temp_dir):
    base = repo_temp_dir / "base.json"
    source = repo_temp_dir / "source.json"
    output = repo_temp_dir / "output.json"
    _write(base, _document("https://base.example"))
    _write(source, _document("https://new.example"))

    assert main(["--base", str(base), "--source", str(source), "--output", str(output)]) == 0
    result = json.loads(output.read_text(encoding="utf-8"))
    assert [p.url for p in visit(parse_json_item(result["roots"]["bookmark_bar"]))] == [
        "https://base.example",
        "https://new.example",
    ]
    assert result["checksum"] == "keep-me"

    assert main(["--base", str(base), "--source", str(source), "--output", str(output)]) != 0


def test_in_place_writes_unique_backup(repo_temp_dir):
    base = repo_temp_dir / "base.json"
    source = repo_temp_dir / "source.json"
    _write(base, _document("https://base.example"))
    _write(source, _document("https://new.example"))
    original = base.read_bytes()

    _, first_backup = write_bookmark_file(base, _document("https://changed.example"), in_place=True)
    _, second_backup = write_bookmark_file(base, _document("https://changed-again.example"), in_place=True)
    assert first_backup != second_backup
    assert Path(first_backup).read_bytes() == original
    assert Path(second_backup).read_bytes() != Path(first_backup).read_bytes()


def test_atomic_write_failure_preserves_original(repo_temp_dir, monkeypatch):
    import src.bookmark_io as bookmark_io

    target = repo_temp_dir / "base.json"
    document = _document("https://base.example")
    _write(target, document)
    original = target.read_bytes()

    def fail_replace(*args):
        raise OSError("simulated replacement failure")

    monkeypatch.setattr(bookmark_io.os, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated"):
        write_bookmark_file(target, document, in_place=True)
    assert target.read_bytes() == original
    assert not list(repo_temp_dir.glob(".bookmarkclearup-*.tmp"))


def test_cli_returns_error_for_missing_input(repo_temp_dir, capsys):
    missing = repo_temp_dir / "missing.json"
    assert main(["--base", str(missing), "--source", str(missing)]) != 0
    assert "error" in capsys.readouterr().err.lower()





