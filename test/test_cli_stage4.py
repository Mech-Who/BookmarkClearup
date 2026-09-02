import json
import pytest
import src.cli as cli
from pathlib import Path
from src.cli import main
from src.bookmark_io import load_chromium_file
from src.html_io import parse_html
from src.functional import visit

FIXTURES = Path(__file__).parent / "fixtures"


def test_mixed_output_dir_keeps_each_input_format_and_shell(repo_temp_dir):
    base = repo_temp_dir / "base.html"
    base.write_bytes((FIXTURES / "chrome_like_bookmarks.html").read_bytes())
    source = repo_temp_dir / "source.json"
    document = json.loads((FIXTURES / "edge_like_bookmarks.json").read_text(encoding="utf-8"))
    document["source_marker"] = "only-source"
    source.write_text(json.dumps(document), encoding="utf-8")
    out = repo_temp_dir / "out"
    assert main(["--base", str(base), "--source", str(source), "--output-dir", str(out)]) == 0
    assert (out / "base_merged.html").is_file()
    assert (out / "source_1_merged.json").is_file()
    assert "https://same.test" in (out / "base_merged.html").read_text(encoding="utf-8")
    assert "https://same.test" in (out / "source_1_merged.json").read_text(encoding="utf-8")
    assert json.loads((out / "source_1_merged.json").read_text(encoding="utf-8"))["source_marker"] == "only-source"


def test_json_to_html_output_dir_and_html_to_json(repo_temp_dir):
    base = repo_temp_dir / "base.json"
    source = repo_temp_dir / "source.json"
    for target, fixture in ((base, "chrome_like_bookmarks.json"), (source, "edge_like_bookmarks.json")):
        target.write_bytes((FIXTURES / fixture).read_bytes())
    html_out = repo_temp_dir / "html"
    assert main(["--base", str(base), "--source", str(source), "--output-dir", str(html_out), "--output-format", "html"]) == 0
    assert len(list(html_out.glob("*.html"))) == 2
    html_base = repo_temp_dir / "base.html"
    html_source = repo_temp_dir / "source.html"
    html_base.write_bytes((FIXTURES / "chrome_like_bookmarks.html").read_bytes())
    html_source.write_bytes((FIXTURES / "edge_like_bookmarks.html").read_bytes())
    json_out = repo_temp_dir / "json"
    assert main(["--base", str(html_base), "--source", str(html_source), "--output-dir", str(json_out), "--output-format", "json"]) == 0
    assert len(list(json_out.glob("*.json"))) == 2
    assert all("roots" in json.loads(path.read_text(encoding="utf-8")) for path in json_out.glob("*.json"))


def test_dry_run_does_not_create_output_dir(repo_temp_dir):
    base = repo_temp_dir / "base.json"
    source = repo_temp_dir / "source.json"
    for target, fixture in ((base, "chrome_like_bookmarks.json"), (source, "edge_like_bookmarks.json")):
        target.write_bytes((FIXTURES / fixture).read_bytes())
    out = repo_temp_dir / "dry"
    assert main(["--base", str(base), "--source", str(source)]) == 0
    assert not out.exists()


def test_html_in_place_cancel_keeps_bytes(repo_temp_dir, monkeypatch):
    base = repo_temp_dir / "base.html"
    source = repo_temp_dir / "source.html"
    base.write_bytes((FIXTURES / "chrome_like_bookmarks.html").read_bytes())
    source.write_bytes((FIXTURES / "edge_like_bookmarks.html").read_bytes())
    original = base.read_bytes()
    monkeypatch.setattr("builtins.input", lambda _: "no")
    assert main(["--base", str(base), "--source", str(source), "--in-place"]) == 2
    assert base.read_bytes() == original


def test_html_in_place_yes_creates_backup(repo_temp_dir):
    base = repo_temp_dir / "base.html"
    source = repo_temp_dir / "source.html"
    base.write_bytes((FIXTURES / "chrome_like_bookmarks.html").read_bytes())
    source.write_bytes((FIXTURES / "edge_like_bookmarks.html").read_bytes())
    assert main(["--base", str(base), "--source", str(source), "--in-place", "--yes"]) == 0
    assert list(repo_temp_dir.glob("base.html.*_bookmark_backup.bak"))


def test_independent_output_failure_rolls_back_created_files(repo_temp_dir, monkeypatch):
    base = repo_temp_dir / "base.json"
    source = repo_temp_dir / "source.json"
    for target, fixture in ((base, "chrome_like_bookmarks.json"), (source, "edge_like_bookmarks.json")):
        target.write_bytes((FIXTURES / fixture).read_bytes())
    original = cli.write_bookmark_file
    def fail_second(path, document, **kwargs):
        if Path(path).name.startswith("source_1"):
            raise OSError("second failure")
        return original(path, document, **kwargs)
    monkeypatch.setattr(cli, "write_bookmark_file", fail_second)
    out = repo_temp_dir / "out"
    assert main(["--base", str(base), "--source", str(source), "--output-dir", str(out)]) == 1
    assert not list(out.glob("*_merged.json"))


def test_in_place_rejects_format_change(repo_temp_dir):
    base = repo_temp_dir / "base.json"
    source = repo_temp_dir / "source.json"
    base.write_bytes((FIXTURES / "chrome_like_bookmarks.json").read_bytes())
    source.write_bytes((FIXTURES / "edge_like_bookmarks.json").read_bytes())
    original = base.read_bytes()
    with pytest.raises(SystemExit):
        main(["--base", str(base), "--source", str(source), "--in-place", "--yes", "--output-format", "html"])
    assert base.read_bytes() == original


def test_html_in_place_replace_failure_preserves_original(repo_temp_dir, monkeypatch):
    import src.safe_file as safe_file
    base = repo_temp_dir / "base.html"
    source = repo_temp_dir / "source.html"
    base.write_bytes((FIXTURES / "chrome_like_bookmarks.html").read_bytes())
    source.write_bytes((FIXTURES / "edge_like_bookmarks.html").read_bytes())
    original = base.read_bytes()
    monkeypatch.setattr(safe_file.os, "replace", lambda *args: (_ for _ in ()).throw(OSError("replace failure")))
    assert main(["--base", str(base), "--source", str(source), "--in-place", "--yes"]) == 1
    assert base.read_bytes() == original


def test_html_in_place_interactive_yes_creates_backup(repo_temp_dir, monkeypatch):
    base = repo_temp_dir / "base.html"
    source = repo_temp_dir / "source.html"
    base.write_bytes((FIXTURES / "chrome_like_bookmarks.html").read_bytes())
    source.write_bytes((FIXTURES / "edge_like_bookmarks.html").read_bytes())
    monkeypatch.setattr("builtins.input", lambda _: "yes")
    assert main(["--base", str(base), "--source", str(source), "--in-place"]) == 0
    assert list(repo_temp_dir.glob("base.html.*_bookmark_backup.bak"))


def test_independent_output_failure_does_not_delete_replaced_file(repo_temp_dir, monkeypatch):
    base = repo_temp_dir / "base.json"
    source = repo_temp_dir / "source.json"
    for target, fixture in ((base, "chrome_like_bookmarks.json"), (source, "edge_like_bookmarks.json")):
        target.write_bytes((FIXTURES / fixture).read_bytes())
    original = cli.write_bookmark_file
    out = repo_temp_dir / "out"
    def replace_then_fail(path, document, **kwargs):
        if Path(path).name.startswith("source_1"):
            (out / "base_merged.json").write_text("external", encoding="utf-8")
            raise OSError("failure")
        return original(path, document, **kwargs)
    monkeypatch.setattr(cli, "write_bookmark_file", replace_then_fail)
    assert main(["--base", str(base), "--source", str(source), "--output-dir", str(out)]) == 1
    assert (out / "base_merged.json").read_text(encoding="utf-8") == "external"


def test_independent_output_cleanup_failure_preserves_original_error(repo_temp_dir, monkeypatch, capsys, caplog):
    import src.cli as cli
    base = repo_temp_dir / "base.json"
    source = repo_temp_dir / "source.json"
    base.write_bytes((FIXTURES / "chrome_like_bookmarks.json").read_bytes())
    source.write_bytes((FIXTURES / "edge_like_bookmarks.json").read_bytes())
    original = cli.write_bookmark_file
    out = repo_temp_dir / "out"
    def fail(path, document, **kwargs):
        if Path(path).name.startswith("source_1"):
            raise OSError("original write failure")
        return original(path, document, **kwargs)
    monkeypatch.setattr(cli, "write_bookmark_file", fail)
    old_unlink = Path.unlink
    def cleanup_fail(path, *args, **kwargs):
        if Path(path).name.startswith("base_merged"):
            raise OSError("cleanup failure")
        return old_unlink(path, *args, **kwargs)
    monkeypatch.setattr(Path, "unlink", cleanup_fail)
    assert main(["--base", str(base), "--source", str(source), "--output-dir", str(out)]) == 1
    assert "original write failure" in capsys.readouterr().err
    assert "cleanup failure" in caplog.text


def test_single_output_json_extension_converts_html_base(repo_temp_dir):
    base = repo_temp_dir / "base.html"
    source = repo_temp_dir / "source.html"
    base.write_bytes((FIXTURES / "chrome_like_bookmarks.html").read_bytes())
    source.write_bytes((FIXTURES / "edge_like_bookmarks.html").read_bytes())
    output = repo_temp_dir / "result.json"
    assert main(["--base", str(base), "--source", str(source), "--output", str(output)]) == 0
    load_chromium_file(output)
    assert not output.read_bytes().startswith(b"<!DOCTYPE")


def test_single_html_output_succeeds_and_refuses_overwrite(repo_temp_dir):
    base = repo_temp_dir / "base.json"
    source = repo_temp_dir / "source.json"
    base_document = json.loads((FIXTURES / "chrome_like_bookmarks.json").read_text(encoding="utf-8"))
    source_document = json.loads((FIXTURES / "edge_like_bookmarks.json").read_text(encoding="utf-8"))
    base_document["roots"]["bookmark_bar"]["children"] = [
        {"name": "Chrome", "type": "url", "url": "https://chrome-source.test", "id": "10", "date_added": "1", "date_last_used": "1"}
    ]
    source_document["roots"]["bookmark_bar"]["children"] = [
        {"name": "Edge", "type": "url", "url": "https://edge-source.test", "id": "11", "date_added": "2", "date_last_used": "2"}
    ]
    base.write_text(json.dumps(base_document), encoding="utf-8")
    source.write_text(json.dumps(source_document), encoding="utf-8")
    output = repo_temp_dir / "result.html"
    args = ["--base", str(base), "--source", str(source), "--output", str(output)]
    assert main(args) == 0
    parsed = parse_html(output)
    urls = {page.url for page in visit(parsed)}
    assert {"https://chrome-source.test", "https://edge-source.test"} <= urls
    original = output.read_bytes()
    assert main(args) == 1
    assert output.read_bytes() == original
def test_other_only_json_cannot_export_html(repo_temp_dir):
    base = repo_temp_dir / "base.json"
    source = repo_temp_dir / "source.json"
    document = {"version": "1", "roots": {"other": {"name": "Other", "type": "folder", "children": []}}}
    base.write_text(json.dumps(document), encoding="utf-8")
    source.write_text(json.dumps(document), encoding="utf-8")
    output = repo_temp_dir / "result.html"
    assert main(["--base", str(base), "--source", str(source), "--output", str(output), "--output-format", "html"]) == 1
    assert not output.exists()