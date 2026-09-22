import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

import src.gui as gui


@pytest.fixture(scope="module")
def app():
    """Provide one offscreen Qt application for GUI tests."""
    instance = QApplication.instance() or QApplication([])
    yield instance


@pytest.fixture
def window(app):
    """Create and dispose the main window for each test."""
    widget = gui.MainWindow()
    yield widget
    widget.close()


def _inputs(window, directory: Path) -> tuple[Path, Path]:
    base = directory / "base.json"
    source = directory / "source.json"
    base.write_text("{}", encoding="utf-8")
    source.write_text("{}", encoding="utf-8")
    window.base_edit.setText(str(base))
    window.add_source_path(source)
    return base, source


def test_default_mode_builds_dry_run_arguments(window, repo_temp_dir):
    base, source = _inputs(window, repo_temp_dir)

    assert window.output_combo.currentData() == "preview"
    assert window.build_arguments() == ["--base", str(base), "--source", str(source)]


@pytest.mark.parametrize(
    ("mode", "flag", "destination"),
    (("single", "--output", "merged.json"), ("directory", "--output-dir", "results")),
)
def test_output_modes_build_expected_arguments(window, repo_temp_dir, mode, flag, destination):
    _inputs(window, repo_temp_dir)
    window.output_combo.setCurrentIndex(window.output_combo.findData(mode))
    target = repo_temp_dir / destination
    window.destination_edit.setText(str(target))
    window.format_combo.setCurrentIndex(window.format_combo.findData("json"))

    arguments = window.build_arguments()

    assert arguments[-4:] == ["--output-format", "json", flag, str(target)]


def test_profile_mode_builds_browser_arguments(window):
    window.profile_radio.setChecked(True)
    window.base_profile.clear()
    window.source_profile.clear()
    window.base_profile.addItem("Default", "Default")
    window.source_profile.addItem("Profile 1", "Profile 1")

    assert window.build_arguments() == [
        "--base-browser", "chrome", "--base-profile", "Default",
        "--source-browser", "edge", "--source-profile", "Profile 1",
    ]


def test_in_place_requires_confirmation(window, repo_temp_dir, monkeypatch):
    _inputs(window, repo_temp_dir)
    window.output_combo.setCurrentIndex(window.output_combo.findData("inplace"))
    started = []

    class FakeSignal:
        def connect(self, callback):
            self.callback = callback

    class FakeThread:
        def __init__(self, arguments, parent):
            self.arguments = arguments
            self.completed = FakeSignal()

        def start(self):
            started.append(self.arguments)

    monkeypatch.setattr(gui, "CommandThread", FakeThread)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Cancel)
    window._run()
    assert started == []

    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    window._run()
    assert started and started[0][-2:] == ["--in-place", "--yes"]


def test_completed_renders_cli_statistics(window):
    window._completed(0, "base=4 sources=5 new=3 result=7\n", "")

    assert {key: label.text() for key, label in window.stat_values.items()} == {
        "base": "4", "sources": "5", "added": "3", "result": "7",
    }
    assert window.status_text.text() == "操作完成"


def test_backup_scan_and_confirmed_cleanup(window, repo_temp_dir, monkeypatch):
    backup = repo_temp_dir / "Bookmarks.20260922_120000_bookmark_backup.bak"
    backup.write_text("backup", encoding="utf-8")
    window.backup_dir.setText(str(repo_temp_dir))
    window.scan_backups()

    assert window.backup_list.count() == 1
    assert window.clean_button.isEnabled()

    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Cancel)
    window.clean_scanned_backups()
    assert backup.exists()

    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    window.clean_scanned_backups()
    assert not backup.exists()


def test_command_thread_captures_cli_output(app, monkeypatch):
    monkeypatch.setattr(gui, "cli_main", lambda arguments: print("base=1 sources=2 new=2 result=3") or 0)
    result = []
    thread = gui.CommandThread(["--base", "base"])
    thread.completed.connect(lambda *values: result.append(values))

    thread.run()

    assert result == [(0, "base=1 sources=2 new=2 result=3\n", "")]
