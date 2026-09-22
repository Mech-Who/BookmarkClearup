"""PySide6 desktop interface for BookmarkClearup."""

from __future__ import annotations

import io
import re
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QDateTime, Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QDateTimeEdit,
    QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit,
    QPushButton, QRadioButton, QStackedWidget, QStyle, QTabWidget,
    QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from src.bookmark_io import clean_backups, list_backups
from src.chromium import discover_profiles
from src.cli import main as cli_main

_STATS = re.compile(
    r"base=(?P<base>\d+)\s+sources=(?P<sources>\d+)\s+"
    r"new=(?P<added>-?\d+)\s+result=(?P<result>\d+)"
)


class CommandThread(QThread):
    """Run the existing CLI contract without blocking the window."""

    completed = Signal(int, str, str)

    def __init__(self, arguments: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.arguments = arguments

    def run(self) -> None:
        """Capture CLI output and return a stable result."""
        stdout, stderr = io.StringIO(), io.StringIO()
        try:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = cli_main(self.arguments)
        except SystemExit as exc:
            code = int(exc.code or 0)
        except Exception as exc:
            code = 1
            stderr.write(f"error: {exc}\n")
        self.completed.emit(code, stdout.getvalue(), stderr.getvalue())


class MainWindow(QMainWindow):
    """Bookmark merge workbench and backup manager."""

    def __init__(self) -> None:
        super().__init__()
        self.command_thread: CommandThread | None = None
        self.setWindowTitle("BookmarkClearup")
        self.resize(1180, 760)
        self.setMinimumSize(1000, 680)
        self._style()
        self._build()
        self._input_changed()
        self._output_changed()
        self._status("等待操作")

    def _style(self) -> None:
        """Apply the restrained, work-focused visual system."""
        self.setStyleSheet("""
        QMainWindow,QWidget#workspace{background:#F4F6F8;color:#17202A}
        QWidget{font-family:"Microsoft YaHei UI","Segoe UI";font-size:13px}
        QFrame#header{background:#FFF;border-bottom:1px solid #DDE3E8}
        QLabel#title{font-family:"Segoe UI","Microsoft YaHei UI";font-size:24px;font-weight:700}
        QLabel#muted{color:#66727D} QLabel#badge{background:#E4F4F1;color:#11685F;
        border:1px solid #B7DED8;border-radius:8px;padding:6px 10px;font-weight:600}
        QTabWidget::pane{border:0} QTabBar::tab{padding:10px 18px;color:#66727D;
        border-bottom:2px solid transparent} QTabBar::tab:selected{color:#167D73;
        border-bottom:2px solid #167D73;font-weight:700}
        QFrame#panel{background:#FFF;border:1px solid #DDE3E8;border-radius:8px}
        QLabel#section{font-size:14px;font-weight:700} QLabel#field{color:#4B5965;font-weight:600}
        QLineEdit,QComboBox,QListWidget,QTreeWidget,QPlainTextEdit,QDateTimeEdit{
        background:#FFF;border:1px solid #C9D2D9;border-radius:6px;padding:7px;
        selection-background-color:#167D73} QLineEdit:focus,QComboBox:focus,
        QListWidget:focus,QTreeWidget:focus,QPlainTextEdit:focus{border:2px solid #167D73}
        QPushButton{min-height:34px;padding:4px 14px;border:1px solid #C9D2D9;
        border-radius:6px;background:#FFF} QPushButton:hover{border-color:#167D73;color:#11685F}
        QPushButton#primary{min-height:42px;background:#167D73;color:#FFF;border:0;font-weight:700}
        QPushButton#danger{background:#B7443E;color:#FFF;border:0;font-weight:700}
        QToolButton{min-width:32px;min-height:32px;border:1px solid #C9D2D9;
        border-radius:6px;background:#FFF} QToolButton:hover{background:#EEF8F6;border-color:#167D73}
        QFrame#stat{background:#FFF;border:1px solid #DDE3E8;border-radius:6px}
        QLabel#statName{color:#66727D;font-size:11px} QLabel#statValue{
        font-family:"Cascadia Mono",Consolas;font-size:22px;font-weight:700}
        QPlainTextEdit{font-family:"Cascadia Mono",Consolas;background:#F9FAFB}
        QLabel#warning{background:#FFF4DE;color:#8C570D;border:1px solid #E7C98F;
        border-radius:6px;padding:8px}
        """)

    def _build(self) -> None:
        """Build header, merge tab, backup tab, and status bar."""
        root = QWidget(objectName="workspace")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        header = QFrame(objectName="header")
        header.setFixedHeight(72)
        row = QHBoxLayout(header)
        name = QVBoxLayout()
        title = QLabel("BookmarkClearup", objectName="title")
        subtitle = QLabel("书签整理工作台", objectName="muted")
        name.addWidget(title)
        name.addWidget(subtitle)
        row.addLayout(name)
        row.addStretch()
        row.addWidget(QLabel("安全模式 · 默认预览", objectName="badge"))
        outer.addWidget(header)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.addTab(self._merge_tab(), "合并书签")
        self.tabs.addTab(self._backup_tab(), "备份管理")
        outer.addWidget(self.tabs, 1)
        self.setCentralWidget(root)
        self.status_text = QLabel()
        self.statusBar().addWidget(self.status_text, 1)

    def _merge_tab(self) -> QWidget:
        page = QWidget()
        row = QHBoxLayout(page)
        row.setContentsMargins(24, 18, 24, 22)
        row.setSpacing(18)
        left = QFrame(objectName="panel")
        left.setFixedWidth(410)
        form = QVBoxLayout(left)
        form.setContentsMargins(20, 18, 20, 18)
        form.addWidget(self._label("输入来源", "section"))

        modes = QHBoxLayout()
        self.file_radio, self.profile_radio = QRadioButton("文件"), QRadioButton("浏览器配置")
        self.file_radio.setChecked(True)
        group = QButtonGroup(self)
        group.addButton(self.file_radio)
        group.addButton(self.profile_radio)
        modes.addWidget(self.file_radio)
        modes.addWidget(self.profile_radio)
        modes.addStretch()
        form.addLayout(modes)

        self.input_stack = QStackedWidget()
        self.input_stack.addWidget(self._file_inputs())
        self.input_stack.addWidget(self._profile_inputs())
        form.addWidget(self.input_stack)
        form.addWidget(self._line())
        form.addWidget(self._label("输出设置", "section"))

        self.output_combo = QComboBox()
        for text, data in (
            ("仅预览", "preview"), ("保存单一结果", "single"),
            ("生成独立结果", "directory"), ("覆盖基准文件", "inplace"),
        ):
            self.output_combo.addItem(text, data)
        form.addWidget(self._field("操作方式", self.output_combo))
        self.format_combo = QComboBox()
        self.format_combo.addItem("自动识别", None)
        self.format_combo.addItem("JSON", "json")
        self.format_combo.addItem("HTML", "html")
        form.addWidget(self._field("输出格式", self.format_combo))

        self.destination_edit = QLineEdit()
        self.destination_button = self._tool(
            QStyle.StandardPixmap.SP_DirOpenIcon, "选择输出位置", self._browse_output
        )
        dest_row = QHBoxLayout()
        dest_row.addWidget(self.destination_edit, 1)
        dest_row.addWidget(self.destination_button)
        self.destination_box = QWidget()
        dest = QVBoxLayout(self.destination_box)
        dest.setContentsMargins(0, 0, 0, 0)
        self.destination_label = self._label("输出位置", "field")
        dest.addWidget(self.destination_label)
        dest.addLayout(dest_row)
        form.addWidget(self.destination_box)
        self.warning = QLabel("覆盖会先生成时间命名备份，并要求再次确认。", objectName="warning")
        self.warning.setWordWrap(True)
        form.addWidget(self.warning)
        form.addStretch()
        self.run_button = QPushButton("预览合并", objectName="primary")
        self.run_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.run_button.clicked.connect(self._run)
        form.addWidget(self.run_button)
        row.addWidget(left)

        right = QVBoxLayout()
        self.stat_values: dict[str, QLabel] = {}
        stats = QHBoxLayout()
        for key, text in (("base", "Base"), ("sources", "Sources"), ("added", "Added"), ("result", "Result")):
            card = QFrame(objectName="stat")
            card.setFixedHeight(76)
            box = QVBoxLayout(card)
            box.addWidget(QLabel(text, objectName="statName"))
            value = QLabel("—", objectName="statValue")
            box.addWidget(value)
            self.stat_values[key] = value
            stats.addWidget(card, 1)
        right.addLayout(stats)
        result_tabs = QTabWidget()
        self.summary = QTreeWidget()
        self.summary.setHeaderLabels(["项目", "内容"])
        self.summary.setRootIsDecorated(False)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("运行记录将在此显示")
        result_tabs.addTab(self.summary, "操作摘要")
        result_tabs.addTab(self.log, "运行记录")
        right.addWidget(result_tabs, 1)
        row.addLayout(right, 1)

        self.file_radio.toggled.connect(self._input_changed)
        self.output_combo.currentIndexChanged.connect(self._output_changed)
        self.format_combo.currentIndexChanged.connect(self._summary)
        self.base_edit.textChanged.connect(self._summary)
        self.destination_edit.textChanged.connect(self._summary)
        return page

    def _file_inputs(self) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.addWidget(self._label("基准书签", "field"))
        base_row = QHBoxLayout()
        self.base_edit = QLineEdit()
        self.base_edit.setPlaceholderText("选择 Bookmarks、JSON 或 HTML")
        base_row.addWidget(self.base_edit, 1)
        base_row.addWidget(self._tool(QStyle.StandardPixmap.SP_FileIcon, "选择基准文件", self._browse_base))
        layout.addLayout(base_row)
        arrow = QLabel("↓  合并")
        arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arrow.setStyleSheet("color:#167D73;font-weight:700;padding:4px")
        layout.addWidget(arrow)
        source_row = QHBoxLayout()
        source_row.addWidget(self._label("来源书签", "field"))
        source_row.addStretch()
        source_row.addWidget(self._tool(QStyle.StandardPixmap.SP_FileDialogNewFolder, "添加来源文件", self._browse_sources))
        source_row.addWidget(self._tool(QStyle.StandardPixmap.SP_TrashIcon, "移除来源文件", self._remove_sources))
        layout.addLayout(source_row)
        self.source_list = QListWidget()
        self.source_list.setMinimumHeight(105)
        layout.addWidget(self.source_list)
        return box

    def _profile_inputs(self) -> QWidget:
        box = QWidget()
        grid = QGridLayout(box)
        self.base_browser, self.source_browser = self._browser(), self._browser("edge")
        self.base_profile, self.source_profile = QComboBox(), QComboBox()
        grid.addWidget(self._label("基准浏览器", "field"), 0, 0)
        grid.addWidget(self._label("基准 Profile", "field"), 0, 1)
        grid.addWidget(self.base_browser, 1, 0)
        grid.addWidget(self.base_profile, 1, 1)
        grid.addWidget(QLabel("↓  合并", alignment=Qt.AlignmentFlag.AlignCenter), 2, 0, 1, 2)
        grid.addWidget(self._label("来源浏览器", "field"), 3, 0)
        grid.addWidget(self._label("来源 Profile", "field"), 3, 1)
        grid.addWidget(self.source_browser, 4, 0)
        grid.addWidget(self.source_profile, 4, 1)
        refresh = QPushButton("刷新 Profile")
        refresh.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        refresh.clicked.connect(self.refresh_profiles)
        grid.addWidget(refresh, 5, 0, 1, 2)
        self.base_browser.currentIndexChanged.connect(self.refresh_profiles)
        self.source_browser.currentIndexChanged.connect(self.refresh_profiles)
        return box

    def _backup_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 22)
        layout.addWidget(self._label("备份管理", "section"))
        top = QHBoxLayout()
        self.backup_dir = QLineEdit()
        self.backup_dir.setPlaceholderText("选择包含 bookmark_backup.bak 的目录")
        top.addWidget(self.backup_dir, 1)
        top.addWidget(self._tool(QStyle.StandardPixmap.SP_DirOpenIcon, "选择备份目录", self._browse_backup))
        scan = QPushButton("扫描备份")
        scan.clicked.connect(self.scan_backups)
        top.addWidget(scan)
        layout.addLayout(top)
        times = QHBoxLayout()
        self.start_check, self.end_check = QCheckBox("起始时间"), QCheckBox("结束时间")
        self.start_time = QDateTimeEdit(QDateTime.currentDateTime().addMonths(-1))
        self.end_time = QDateTimeEdit(QDateTime.currentDateTime())
        for control in (self.start_time, self.end_time):
            control.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
            control.setCalendarPopup(True)
            control.setEnabled(False)
        self.start_check.toggled.connect(self.start_time.setEnabled)
        self.end_check.toggled.connect(self.end_time.setEnabled)
        for widget in (self.start_check, self.start_time, self.end_check, self.end_time):
            times.addWidget(widget)
        times.addStretch()
        layout.addLayout(times)
        self.backup_list = QListWidget()
        self.backup_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        layout.addWidget(self.backup_list, 1)
        foot = QHBoxLayout()
        self.backup_count = QLabel("尚未扫描")
        self.clean_button = QPushButton("清理列表中的备份", objectName="danger")
        self.clean_button.setEnabled(False)
        self.clean_button.clicked.connect(self.clean_scanned_backups)
        foot.addWidget(self.backup_count)
        foot.addStretch()
        foot.addWidget(self.clean_button)
        layout.addLayout(foot)
        return page

    def _label(self, text: str, name: str) -> QLabel:
        return QLabel(text, objectName=name)

    def _field(self, text: str, widget: QWidget) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label(text, "field"))
        layout.addWidget(widget)
        return box

    def _line(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        return line

    def _tool(self, icon: QStyle.StandardPixmap, tip: str, callback) -> QToolButton:
        button = QToolButton()
        button.setIcon(self.style().standardIcon(icon))
        button.setToolTip(tip)
        button.clicked.connect(callback)
        return button

    def _browser(self, value: str = "chrome") -> QComboBox:
        combo = QComboBox()
        combo.addItem("Chrome", "chrome")
        combo.addItem("Edge", "edge")
        combo.setCurrentIndex(0 if value == "chrome" else 1)
        return combo

    def _browse_base(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择基准书签", "", "书签文件 (Bookmarks *.json *.html *.htm);;所有文件 (*)")
        if path:
            self.base_edit.setText(path)

    def _browse_sources(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "添加来源书签", "", "书签文件 (Bookmarks *.json *.html *.htm);;所有文件 (*)")
        for path in paths:
            self.add_source_path(path)

    def add_source_path(self, path: str | Path) -> None:
        """Add a source file once."""
        value = str(Path(path))
        current = {self.source_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.source_list.count())}
        if value not in current:
            item = QListWidgetItem(Path(value).name or value)
            item.setData(Qt.ItemDataRole.UserRole, value)
            item.setToolTip(value)
            self.source_list.addItem(item)
        self._summary()

    def _remove_sources(self) -> None:
        for item in self.source_list.selectedItems():
            self.source_list.takeItem(self.source_list.row(item))
        self._summary()

    def _browse_output(self) -> None:
        if self.output_combo.currentData() == "single":
            path, _ = QFileDialog.getSaveFileName(self, "保存结果", "", "JSON (*.json);;HTML (*.html *.htm)")
        else:
            path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if path:
            self.destination_edit.setText(path)

    def _browse_backup(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择备份目录")
        if path:
            self.backup_dir.setText(path)

    def _input_changed(self) -> None:
        self.input_stack.setCurrentIndex(0 if self.file_radio.isChecked() else 1)
        if self.profile_radio.isChecked():
            self.refresh_profiles()
        self._summary()

    def _output_changed(self) -> None:
        mode = self.output_combo.currentData()
        self.destination_box.setVisible(mode in {"single", "directory"})
        self.warning.setVisible(mode == "inplace")
        self.run_button.setText({"preview": "预览合并", "single": "生成结果", "directory": "生成独立结果", "inplace": "确认并覆盖"}[mode])
        self.destination_label.setText("输出文件" if mode == "single" else "输出目录")
        self._summary()

    def refresh_profiles(self) -> None:
        """Scan Chrome and Edge profiles."""
        for browsers, profiles in ((self.base_browser, self.base_profile), (self.source_browser, self.source_profile)):
            profiles.clear()
            try:
                names = discover_profiles(browsers.currentData())
            except (OSError, ValueError) as exc:
                profiles.addItem("未找到 Profile", None)
                profiles.setToolTip(str(exc))
                continue
            for name in names:
                profiles.addItem(name, name)
        self._summary()

    def build_arguments(self) -> list[str]:
        """Validate controls and build the existing CLI arguments."""
        args: list[str] = []
        if self.file_radio.isChecked():
            base = Path(self.base_edit.text().strip())
            if not base.is_file():
                raise ValueError("请选择有效的基准书签文件")
            sources = [Path(self.source_list.item(i).data(Qt.ItemDataRole.UserRole)) for i in range(self.source_list.count())]
            if not sources:
                raise ValueError("请至少添加一个来源书签文件")
            missing = next((path for path in sources if not path.is_file()), None)
            if missing:
                raise ValueError(f"来源文件不存在：{missing}")
            args.extend(["--base", str(base), "--source", *(str(path) for path in sources)])
        else:
            base_profile, source_profile = self.base_profile.currentData(), self.source_profile.currentData()
            if not base_profile or not source_profile:
                raise ValueError("请选择有效的基准和来源 Profile")
            args.extend(["--base-browser", self.base_browser.currentData(), "--base-profile", base_profile,
                         "--source-browser", self.source_browser.currentData(), "--source-profile", source_profile])
        if self.format_combo.currentData():
            args.extend(["--output-format", self.format_combo.currentData()])
        mode = self.output_combo.currentData()
        if mode in {"single", "directory"}:
            destination = self.destination_edit.text().strip()
            if not destination:
                raise ValueError("请选择输出位置")
            args.extend(["--output" if mode == "single" else "--output-dir", destination])
        elif mode == "inplace":
            args.append("--in-place")
        return args

    def _run(self) -> None:
        try:
            args = self.build_arguments()
        except ValueError as exc:
            self._status(str(exc), True)
            QMessageBox.warning(self, "输入不完整", str(exc))
            return
        if self.output_combo.currentData() == "inplace":
            answer = QMessageBox.question(self, "确认覆盖", "将覆盖基准书签并生成备份。是否继续？",
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                                          QMessageBox.StandardButton.Cancel)
            if answer != QMessageBox.StandardButton.Yes:
                self._status("已取消覆盖")
                return
            args.append("--yes")
        self._summary()
        self.log.clear()
        self.log.appendPlainText("$ bookmarkclearup " + " ".join(args))
        self.run_button.setEnabled(False)
        self._status("正在处理…")
        self.command_thread = CommandThread(args, self)
        self.command_thread.completed.connect(self._completed)
        self.command_thread.start()

    def _completed(self, code: int, stdout: str, stderr: str) -> None:
        """Render command output and restore controls."""
        for text in (stdout.strip(), stderr.strip()):
            if text:
                self.log.appendPlainText(text)
        match = _STATS.search(stdout)
        if match:
            for key in self.stat_values:
                self.stat_values[key].setText(match.group(key))
        self._status("操作完成" if code == 0 else f"操作失败（退出码 {code}）", code != 0)
        self.run_button.setEnabled(True)
        self.command_thread = None

    def _summary(self) -> None:
        if not hasattr(self, "summary"):
            return
        self.summary.clear()
        mode = "文件" if self.file_radio.isChecked() else "浏览器配置"
        rows = [("输入方式", mode), ("操作", self.output_combo.currentText()), ("格式", self.format_combo.currentText())]
        if self.file_radio.isChecked():
            rows.insert(1, ("基准", self.base_edit.text().strip() or "未选择"))
            rows.insert(2, ("来源", f"{self.source_list.count()} 个文件"))
        else:
            rows.insert(1, ("基准", f"{self.base_browser.currentText()} / {self.base_profile.currentText()}"))
            rows.insert(2, ("来源", f"{self.source_browser.currentText()} / {self.source_profile.currentText()}"))
        if self.output_combo.currentData() in {"single", "directory"}:
            rows.append(("目标", self.destination_edit.text().strip() or "未选择"))
        for key, value in rows:
            QTreeWidgetItem(self.summary, [key, value])
        self.summary.resizeColumnToContents(0)

    def _status(self, text: str, error: bool = False) -> None:
        self.status_text.setText(text)
        self.status_text.setStyleSheet(f"color:{'#B7443E' if error else '#66727D'};font-weight:600")

    def _range(self) -> tuple[datetime | None, datetime | None]:
        start = self.start_time.dateTime().toPython() if self.start_check.isChecked() else None
        end = self.end_time.dateTime().toPython() if self.end_check.isChecked() else None
        return start, end

    def scan_backups(self) -> None:
        """List backups within the selected range."""
        directory = Path(self.backup_dir.text().strip())
        if not directory.is_dir():
            self._status("请选择有效的备份目录", True)
            return
        try:
            backups = list_backups(directory, *self._range())
        except (OSError, ValueError) as exc:
            self._status(str(exc), True)
            return
        self.backup_list.clear()
        for path in backups:
            item = QListWidgetItem(path.name)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            item.setToolTip(str(path))
            self.backup_list.addItem(item)
        self.backup_count.setText(f"找到 {len(backups)} 个备份")
        self.clean_button.setEnabled(bool(backups))
        self._status("备份扫描完成")

    def clean_scanned_backups(self) -> None:
        """Delete scanned backups only after confirmation."""
        if not self.backup_list.count():
            return
        answer = QMessageBox.question(self, "确认清理", f"将删除 {self.backup_list.count()} 个备份。是否继续？",
                                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                                      QMessageBox.StandardButton.Cancel)
        if answer != QMessageBox.StandardButton.Yes:
            self._status("已取消备份清理")
            return
        try:
            clean_backups(Path(self.backup_dir.text().strip()), start=self._range()[0],
                          end=self._range()[1], dry_run=False, confirm=True)
        except (OSError, ValueError) as exc:
            self._status(str(exc), True)
            return
        self.scan_backups()
        self._status("备份清理完成")


def main() -> int:
    """Create and run the desktop application."""
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("BookmarkClearup")
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei UI", 10))
    window = MainWindow()
    window.show()
    return app.exec()

