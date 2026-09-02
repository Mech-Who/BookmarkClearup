import json
from pathlib import Path

import pytest

from src.bookmark_io import load_chromium_file, merge_documents, output_documents, write_bookmark_file
from src.chromium import browser_user_data_dir, discover_profiles
from src.cli import main


def folder(name, url=None, stamp="1"):
    """Build a minimal Chromium folder fixture."""
    children = []
    if url is not None:
        children.append({"name": name, "type": "url", "url": url, "id": "2", "date_added": stamp, "date_last_used": stamp})
    return {"name": name, "type": "folder", "children": children, "id": "1", "date_added": stamp, "date_last_used": stamp, "date_modified": stamp}


def document(root_names, *, marker):
    """Build a Chromium-like document with vendor fields."""
    roots = {name: folder(name, f"https://{marker}-{name}.example") for name in root_names}
    roots["unknown_root"] = {"vendor": marker}
    return {"checksum": f"checksum-{marker}", "vendor_field": marker, "roots": roots}


def write(path, value):
    """Write a JSON test fixture."""
    path.write_text(json.dumps(value), encoding="utf-8")


def test_multi_root_merge_keeps_shells_and_missing_roots(repo_temp_dir):
    base = repo_temp_dir / "base.json"
    source = repo_temp_dir / "source.json"
    write(base, document(["bookmark_bar", "other"], marker="base"))
    write(source, document(["other", "synced"], marker="source"))
    base_doc, base_roots = load_chromium_file(base)
    source_doc, source_roots = load_chromium_file(source)
    merged = merge_documents(base_roots, source_roots)
    outputs = output_documents([(base_doc, base_roots), (source_doc, source_roots)], merged)
    assert set(merged) == {"bookmark_bar", "other", "synced"}
    assert outputs[0]["checksum"] == "checksum-base"
    assert outputs[1]["vendor_field"] == "source"
    assert outputs[0]["roots"]["unknown_root"] == {"vendor": "base"}
    assert outputs[1]["roots"]["unknown_root"] == {"vendor": "source"}
    assert "synced" in outputs[0]["roots"] and "bookmark_bar" in outputs[1]["roots"]


def test_missing_all_supported_roots_is_rejected(repo_temp_dir):
    path = repo_temp_dir / "bad.json"
    write(path, {"roots": {"unknown": {}}})
    with pytest.raises(ValueError, match="supported root"):
        load_chromium_file(path)


def test_profile_discovery_and_browser_paths(repo_temp_dir, monkeypatch):
    local = repo_temp_dir / "local"
    user_data = local / "Google" / "Chrome" / "User Data"
    (user_data / "Default").mkdir(parents=True)
    (user_data / "Profile 1").mkdir()
    (user_data / "Default" / "Bookmarks").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    assert browser_user_data_dir("chrome") == user_data
    assert discover_profiles("chrome") == ["Default", "Profile 1"]


def test_cli_browser_and_explicit_paths_are_mutually_exclusive():
    with pytest.raises(SystemExit) as exc:
        main(["--base", "base", "--source", "source", "--base-browser", "chrome"])
    assert exc.value.code == 2


def test_cli_independent_outputs(repo_temp_dir):
    base = repo_temp_dir / "base.json"
    source = repo_temp_dir / "source.json"
    output_dir = repo_temp_dir / "out"
    write(base, document(["bookmark_bar"], marker="base"))
    write(source, document(["bookmark_bar"], marker="source"))
    assert main(["--base", str(base), "--source", str(source), "--output-dir", str(output_dir)]) == 0
    assert (output_dir / "base_merged.json").exists()
    assert (output_dir / "source_1_merged.json").exists()
    assert main(["--base", str(base), "--source", str(source), "--output-dir", str(output_dir)]) != 0


def test_other_only_document_can_be_written(repo_temp_dir):
    base = repo_temp_dir / "base.json"
    source = repo_temp_dir / "source.json"
    output = repo_temp_dir / "output.json"
    write(base, document(["other"], marker="base"))
    write(source, document(["other"], marker="source"))
    assert main(["--base", str(base), "--source", str(source), "--output", str(output)]) == 0
    assert output.exists()


def test_independent_outputs_roll_back_on_second_failure(repo_temp_dir, monkeypatch):
    base = repo_temp_dir / "base.json"
    source = repo_temp_dir / "source.json"
    output_dir = repo_temp_dir / "out"
    write(base, document(["bookmark_bar"], marker="base"))
    write(source, document(["bookmark_bar"], marker="source"))
    import src.cli as cli
    original_write = cli.write_bookmark_file

    def fail_second(path, document, **kwargs):
        if Path(path).name == "source_1_merged.json":
            raise OSError("simulated second output failure")
        return original_write(path, document, **kwargs)

    monkeypatch.setattr(cli, "write_bookmark_file", fail_second)
    assert main(["--base", str(base), "--source", str(source), "--output-dir", str(output_dir)]) == 1
    assert not list(output_dir.glob("*_merged.json"))

def test_fixture_round_trip_preserves_independent_shells(repo_temp_dir):
    """Verify both supplied Chromium-like fixtures through safe round-trip IO."""
    fixture_dir = Path(__file__).parent / "fixtures"
    paths = [repo_temp_dir / "chrome.json", repo_temp_dir / "edge.json"]
    for destination, name in zip(paths, ("chrome_like_bookmarks.json", "edge_like_bookmarks.json")):
        destination.write_bytes((fixture_dir / name).read_bytes())
    inputs = [load_chromium_file(path) for path in paths]
    merged = merge_documents(*(roots for _, roots in inputs))
    outputs = output_documents(inputs, merged)
    reparsed = []
    for index, output in enumerate(outputs):
        destination = repo_temp_dir / f"roundtrip_{index}.json"
        write_bookmark_file(destination, output, output=True)
        reparsed.append(load_chromium_file(destination))
    assert reparsed[0][1].keys() == reparsed[1][1].keys()
    for name in merged:
        assert output_documents([reparsed[0]], merged)[0]["roots"][name] == output_documents([reparsed[1]], merged)[0]["roots"][name]
    assert reparsed[0][0]["checksum"] == "chrome-checksum"
    assert reparsed[1][0]["checksum"] == "edge-checksum"
    assert reparsed[0][0]["roots"]["vendor_root"] == {"keep": True}
    assert reparsed[1][0]["roots"]["vendor_root"] == {"keep": False}


def test_cli_profile_success_creates_independent_outputs(repo_temp_dir, monkeypatch):
    """Verify Chrome and Edge Profile selection through the CLI."""
    local = repo_temp_dir / "local"
    chrome = local / "Google" / "Chrome" / "User Data" / "Default"
    edge = local / "Microsoft" / "Edge" / "User Data" / "Profile 1"
    chrome.mkdir(parents=True)
    edge.mkdir(parents=True)
    fixture_dir = Path(__file__).parent / "fixtures"
    (chrome / "Bookmarks").write_bytes((fixture_dir / "chrome_like_bookmarks.json").read_bytes())
    (edge / "Bookmarks").write_bytes((fixture_dir / "edge_like_bookmarks.json").read_bytes())
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    output_dir = repo_temp_dir / "profile-output"
    assert main(["--base-browser", "chrome", "--base-profile", "Default", "--source-browser", "edge", "--source-profile", "Profile 1", "--output-dir", str(output_dir)]) == 0
    assert (output_dir / "Bookmarks_merged.json").exists()
    assert (output_dir / "source_1_merged.json").exists()


def test_cleanup_rejects_browser_profile_options():
    """Ensure cleanup mode cannot be combined with browser/profile mode."""
    with pytest.raises(SystemExit) as exc:
        main(["--clean-backups", "backups", "--base-browser", "chrome", "--base-profile", "Default"])
    assert exc.value.code == 2


def test_independent_outputs_keep_external_replacement(repo_temp_dir, monkeypatch):
    """Do not remove a first output replaced externally before failure."""
    base = repo_temp_dir / "base.json"
    source = repo_temp_dir / "source.json"
    output_dir = repo_temp_dir / "out"
    write(base, document(["bookmark_bar"], marker="base"))
    write(source, document(["bookmark_bar"], marker="source"))
    import src.cli as cli
    original_write = cli.write_bookmark_file

    def replace_first_then_fail(path, value, **kwargs):
        if Path(path).name == "source_1_merged.json":
            (output_dir / "base_merged.json").write_text("external", encoding="utf-8")
            raise OSError("second failure")
        return original_write(path, value, **kwargs)

    monkeypatch.setattr(cli, "write_bookmark_file", replace_first_then_fail)
    assert main(["--base", str(base), "--source", str(source), "--output-dir", str(output_dir)]) == 1
    assert (output_dir / "base_merged.json").read_text(encoding="utf-8") == "external"


def test_independent_outputs_preserve_original_error_when_cleanup_fails(repo_temp_dir, monkeypatch, capsys):
    """Cleanup errors must not mask the original write failure."""
    base = repo_temp_dir / "base.json"
    source = repo_temp_dir / "source.json"
    output_dir = repo_temp_dir / "out"
    write(base, document(["bookmark_bar"], marker="base"))
    write(source, document(["bookmark_bar"], marker="source"))
    import src.cli as cli
    original_write = cli.write_bookmark_file
    original_unlink = Path.unlink

    def fail_second(path, value, **kwargs):
        if Path(path).name == "source_1_merged.json":
            raise OSError("original second failure")
        return original_write(path, value, **kwargs)

    def fail_cleanup(path, *args, **kwargs):
        if Path(path).name == "base_merged.json":
            raise OSError("cleanup failure")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(cli, "write_bookmark_file", fail_second)
    monkeypatch.setattr(Path, "unlink", fail_cleanup)
    assert main(["--base", str(base), "--source", str(source), "--output-dir", str(output_dir)]) == 1
    assert "original second failure" in capsys.readouterr().err