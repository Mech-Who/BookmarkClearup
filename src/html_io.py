"""Netscape Bookmark HTML import and export."""
from __future__ import annotations

import html
import os
import tempfile
from pathlib import Path
from lxml import etree

UNIX_EPOCH_MAX = 253402300799
_EPOCH_OFFSET = 11644473600


def html_seconds_to_chromium(value: str | int | None) -> str | None:
    """Convert HTML Unix seconds to Chromium WebKit microseconds."""
    if value in (None, ""):
        return None
    try:
        seconds = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid HTML timestamp: {value!r}") from exc
    if seconds < 0 or seconds > UNIX_EPOCH_MAX:
        raise ValueError(f"HTML timestamp out of range: {value!r}")
    return str((seconds + _EPOCH_OFFSET) * 1000000)


def chromium_to_html_seconds(value: str | int | None) -> str | None:
    """Convert Chromium WebKit microseconds (or legacy Unix seconds) to HTML seconds."""
    if value in (None, ""):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid Chromium timestamp: {value!r}") from exc
    seconds = number if number < 1000000000000 else number // 1000000 - _EPOCH_OFFSET
    if seconds < 0 or seconds > UNIX_EPOCH_MAX:
        raise ValueError(f"Chromium timestamp out of range: {value!r}")
    return str(seconds)


def _attribute(node: etree._Element, name: str) -> str | None:
    """Read an HTML attribute regardless of parser case normalization."""
    return node.get(name) or node.get(name.lower()) or node.get(name.upper())


def _stamp(value: str | None) -> str | None:
    """Map an HTML Unix timestamp to the model's Chromium timestamp."""
    return html_seconds_to_chromium(value)


def _set_paths(folder: "BookmarkFolder", parent: "BookmarkFolder | None") -> None:
    """Recursively restore parent and path links after parsing."""
    folder.parent = parent
    folder.path = parent.path / folder.name if parent else Path("/")
    for child in folder.children:
        child.parent = folder
        child.path = folder.path / child.name
        from src.entity import BookmarkFolder
        if isinstance(child, BookmarkFolder):
            _set_paths(child, folder)


def _parse_tree(dl: etree._Element, parent: "BookmarkFolder | None" = None) -> "BookmarkFolder":
    """Parse only DT entries whose immediately following sibling is their DL."""
    from src.entity import BookmarkFolder, BookmarkPage
    root = BookmarkFolder(name="Bookmarks", parent=parent)
    entries = []
    for candidate in dl.xpath(".//dt"):

        nearest_dl = candidate.xpath("ancestor::dl[1]")[0]
        if nearest_dl is dl:
            entries.append(candidate)
    for dt in entries:
        node = next((item for item in dt if etree.QName(item).localname.upper() in ("H3", "A")), None)
        if node is None:
            continue
        tag = etree.QName(node).localname.upper()
        title = "".join(node.itertext())
        if tag == "H3":
            folder = BookmarkFolder(
                name=title,
                parent=root,
                path=root.path / title,
                date_added=_stamp(_attribute(node, "ADD_DATE")),
                date_modified=_stamp(_attribute(node, "LAST_MODIFIED")),
            )
            # 1. Skip optional P nodes and locate the folder DL sibling.
            sibling = dt.getnext()
            while sibling is not None and etree.QName(sibling).localname.lower() == "p":
                sibling = sibling.getnext()
            if sibling is not None and etree.QName(sibling).localname.upper() == "DL":
                # 2. Recursively parse the folder and attach its children.
                parsed = _parse_tree(sibling, folder)
                folder.children = parsed.children
                _set_paths(folder, root)
            root.append(folder)
        elif tag == "A":
            url = _attribute(node, "HREF")
            if not url:
                continue
            root.append(BookmarkPage(
                url=url,
                name=title,
                parent=root,
                path=root.path / title,
                date_added=_stamp(_attribute(node, "ADD_DATE")),
                date_last_used=_stamp(_attribute(node, "LAST_MODIFIED")),
                type="url",
            ))
    return root


def parse_html(source: str | Path) -> "BookmarkFolder":
    """Parse a UTF-8 Netscape Bookmark HTML file into a tree."""
    from src.entity import BookmarkFolder
    path = Path(source)
    parser = etree.HTMLParser(encoding="utf-8", recover=True)
    tree = etree.HTML(path.read_bytes(), parser)
    if tree is None:
        raise ValueError(f"invalid HTML bookmark file: {path}")
    dl = tree.xpath("//dl[1]")
    if not dl:
        raise ValueError(f"HTML bookmark file has no DL: {path}")
    root = _parse_tree(dl[0])
    heading = tree.xpath("string((//h1 | //title)[1])")
    if heading.strip():
        root.name = heading.strip()
    _set_paths(root, None)
    return root


def _escape(value: str) -> str:
    """Escape text or attribute data for HTML output."""
    return html.escape(value, quote=True)


def _render(folder: "BookmarkFolder", depth: int = 0) -> list[str]:
    """Render a folder recursively in Netscape's permissive DL form."""
    from src.entity import BookmarkFolder, BookmarkPage
    indent = "    " * depth
    lines = [f"{indent}<DL><p>"]
    for child in folder.children:
        if isinstance(child, BookmarkFolder):
            added = chromium_to_html_seconds(child.date_added) or "0"
            modified = chromium_to_html_seconds(child.date_modified)
            attrs = f' ADD_DATE="{_escape(added)}"'
            if modified is not None:
                attrs += f' LAST_MODIFIED="{_escape(modified)}"'
            lines.append(f"{indent}<DT><H3{attrs}>{_escape(child.name)}</H3>")
            lines.extend(_render(child, depth + 1))
        elif isinstance(child, BookmarkPage):
            added = chromium_to_html_seconds(child.date_added) or "0"
            modified = chromium_to_html_seconds(child.date_last_used)
            attrs = f' HREF="{_escape(child.url)}" ADD_DATE="{_escape(added)}"'
            if modified is not None:
                attrs += f' LAST_MODIFIED="{_escape(modified)}"'
            lines.append(f"{indent}<DT><A{attrs}>{_escape(child.name)}</A>")
    lines.append(f"{indent}</DL><p>")
    return lines


def dumps_html(folder: "BookmarkFolder") -> str:
    """Serialize a bookmark tree as UTF-8 Netscape Bookmark HTML."""
    title = _escape(folder.name or "Bookmarks")
    lines = ["<!DOCTYPE NETSCAPE-Bookmark-file-1>", '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">', f"<TITLE>{title}</TITLE>", f"<H1>{title}</H1>"]
    lines.extend(_render(folder))
    return "\n".join(lines) + "\n"


def dump_html(folder: "BookmarkFolder", destination: str | Path) -> None:
    """Write a new HTML output without overwriting an existing file."""
    write_html_file(destination, folder, output=True)

def write_html_file(path: str | Path, folder: "BookmarkFolder", *, output: bool = False, in_place: bool = False, confirm: bool = False) -> tuple[Path, Path | None]:
    """Safely write a new HTML file or confirmed in-place replacement."""
    from src.safe_file import atomic_write
    target = Path(path)
    backup = atomic_write(target, dumps_html(folder), parse_html, output=output, in_place=in_place, confirm=confirm)
    return target, backup