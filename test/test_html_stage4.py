from pathlib import Path
import pytest
from src.html_io import chromium_to_html_seconds, dumps_html, html_seconds_to_chromium, parse_html
from src.functional import merge, visit

FIXTURES = Path(__file__).parent / "fixtures"

def test_html_fixture_preserves_tree_and_metadata():
    root = parse_html(FIXTURES / "chrome_like_bookmarks.html")
    folder = root.children[0]
    nested = folder.children[0]
    page = nested.children[0]
    assert root.name == "Chrome & Test"
    assert page.url == "https://same.test/?a=1&b=2"
    assert page.parent is nested
    assert page.path == Path('/') / 'Work & "One"' / "Nested" / "A <link>"
    assert chromium_to_html_seconds(page.date_added) == "1700000002"
    assert nested.parent is folder

def test_html_time_conversion_boundaries_and_invalid_values():
    assert html_seconds_to_chromium("0") == "11644473600000000"
    assert chromium_to_html_seconds(html_seconds_to_chromium("253402300799")) == "253402300799"
    for converter in (html_seconds_to_chromium, chromium_to_html_seconds):
        with pytest.raises(ValueError):
            converter("bad")
        with pytest.raises(ValueError):
            converter("-1")

def test_html_dump_escape_and_roundtrip(repo_temp_dir):
    root = parse_html(FIXTURES / "chrome_like_bookmarks.html")
    output = repo_temp_dir / "roundtrip.html"
    output.write_text(dumps_html(root), encoding="utf-8")
    reparsed = parse_html(output)
    pages = list(visit(reparsed))
    assert pages[0].name == "A <link>"
    assert "&amp;" in output.read_text(encoding="utf-8")
    assert pages[0].parent.name == "Nested"

def test_html_merge_uses_newer_record_and_keeps_directories():
    base = parse_html(FIXTURES / "chrome_like_bookmarks.html")
    source = parse_html(FIXTURES / "edge_like_bookmarks.html")
    merged = merge(base, source)
    pages = list(visit(merged))
    same = [page for page in pages if page.url == "https://same.test/?a=1&b=2"]
    assert len(same) == 2
    assert any(page.name == "New & Better" for page in same)
def test_html_safe_output_refuses_existing_and_in_place_requires_confirmation(repo_temp_dir):
    from src.html_io import write_html_file
    root = parse_html(FIXTURES / "chrome_like_bookmarks.html")
    target = repo_temp_dir / "out.html"
    write_html_file(target, root, output=True)
    with pytest.raises(FileExistsError):
        write_html_file(target, root, output=True)
    original = target.read_bytes()
    with pytest.raises(PermissionError):
        write_html_file(target, root, in_place=True)
    assert target.read_bytes() == original


def test_html_safe_in_place_creates_backup(repo_temp_dir):
    from src.html_io import write_html_file
    root = parse_html(FIXTURES / "chrome_like_bookmarks.html")
    target = repo_temp_dir / "bookmarks.html"
    target.write_bytes(dumps_html(root).encode("utf-8"))
    original = target.read_bytes()
    _, backup = write_html_file(target, root, in_place=True, confirm=True)
    assert backup is not None
    assert backup.read_bytes() == original
    assert target.read_bytes() == original
def test_both_fixtures_safe_write_roundtrip(repo_temp_dir):
    from src.html_io import write_html_file
    for name in ("chrome_like_bookmarks.html", "edge_like_bookmarks.html"):
        root = parse_html(FIXTURES / name)
        target = repo_temp_dir / name
        write_html_file(target, root, output=True)
        reparsed = parse_html(target)
        assert [(page.name, page.url) for page in visit(reparsed)] == [(page.name, page.url) for page in visit(root)]