import json
import shutil
import uuid
from datetime import datetime
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

def test_in_place_requires_explicit_confirmation(repo_temp_dir, monkeypatch):
    base = repo_temp_dir / "base.json"
    source = repo_temp_dir / "source.json"
    _write(base, _document("https://base.example"))
    _write(source, _document("https://new.example"))
    before = base.read_bytes()
    monkeypatch.setattr("builtins.input", lambda _: "no")
    assert main(["--base", str(base), "--source", str(source), "--in-place"]) == 2
    assert base.read_bytes() == before


def test_yes_allows_in_place_and_uses_named_backup(repo_temp_dir):
    base = repo_temp_dir / "base.json"
    source = repo_temp_dir / "source.json"
    _write(base, _document("https://base.example"))
    _write(source, _document("https://new.example"))
    assert main(["--base", str(base), "--source", str(source), "--in-place", "--yes"]) == 0
    backups = list(repo_temp_dir.glob("base.json.*_bookmark_backup*.bak"))
    assert len(backups) == 1


def test_backup_cleanup_is_dry_run_until_confirmed(repo_temp_dir):
    from src.bookmark_io import clean_backups, list_backups
    base = repo_temp_dir / "base.json"; _write(base, _document("https://base.example"))
    write_bookmark_file(base, _document("https://changed.example"), in_place=True)
    backups = list_backups(repo_temp_dir)
    assert len(backups) == 1
    assert clean_backups(repo_temp_dir, dry_run=True) == backups
    assert backups[0].exists()
    assert clean_backups(repo_temp_dir, dry_run=False, confirm=True) == backups
    assert not backups[0].exists()

def test_cli_backup_cleanup_lists_then_deletes_with_yes(repo_temp_dir, capsys):
    from src.bookmark_io import list_backups
    base = repo_temp_dir / "base.json"; _write(base, _document("https://base.example"))
    write_bookmark_file(base, _document("https://changed.example"), in_place=True)
    assert main(["--clean-backups", str(repo_temp_dir)]) == 0
    assert len(list_backups(repo_temp_dir)) == 1
    assert main(["--clean-backups", str(repo_temp_dir), "--yes"]) == 0
    assert list_backups(repo_temp_dir) == []


def test_output_race_does_not_overwrite_new_target(repo_temp_dir, monkeypatch):
    import src.bookmark_io as bookmark_io
    base = repo_temp_dir / "base.json"; output = repo_temp_dir / "output.json"
    document = _document("https://base.example"); _write(base, document)
    original = b"race-owner"
    def race_link(temp, target):
        Path(target).write_bytes(original)
        raise FileExistsError("target appeared")
    monkeypatch.setattr(bookmark_io.os, "link", race_link)
    with pytest.raises(FileExistsError):
        write_bookmark_file(output, document, output=True)
    assert output.read_bytes() == original


def test_backup_cleanup_time_bounds_are_inclusive_and_strict(repo_temp_dir):
    from src.bookmark_io import list_backups
    inside_start = repo_temp_dir / "a.json.20260901_000000_bookmark_backup.bak"
    inside_end = repo_temp_dir / "b.json.20260902_000000_bookmark_backup.bak"
    outside = repo_temp_dir / "c.json.20260903_000000_bookmark_backup.bak"
    unrelated = repo_temp_dir / "not-a-tool-backup.bak"
    for path in (inside_start, inside_end, outside, unrelated):
        path.write_text("x", encoding="utf-8")
    found = list_backups(repo_temp_dir, datetime(2026, 9, 1), datetime(2026, 9, 2))
    assert found == [inside_start, inside_end]
    assert outside.exists() and unrelated.exists()


def test_backup_time_arguments_without_cleanup_are_rejected():
    with pytest.raises(SystemExit) as exc:
        main(["--start", "20260901_000000", "--base", "base", "--source", "source"])
    assert exc.value.code == 2


def test_invalid_backup_time_returns_cli_error(repo_temp_dir, capsys):
    assert main(["--clean-backups", str(repo_temp_dir), "--start", "invalid"]) == 1
    assert "error" in capsys.readouterr().err.lower()