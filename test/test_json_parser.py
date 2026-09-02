import pytest

from src.entity import BookmarkFolder, BookmarkPage
from src.functional import parse_json_item, visit


def test_parse_json_item_builds_nested_folder_and_visits_pages():
    bookmark_json = {
        "children": [
            {"date_added": "1", "date_last_used": "0", "guid": "page-guid", "id": "2", "name": "Example", "type": "url", "url": "https://example.com"},
            {"children": [{"date_added": "3", "date_last_used": "0", "guid": "nested-guid", "id": "4", "name": "Nested", "type": "url", "url": "https://nested.example.com"}], "date_added": "5", "date_last_used": "0", "date_modified": "5", "guid": "folder-guid", "id": "6", "name": "Nested folder", "type": "folder"},
        ],
        "date_added": "7", "date_last_used": "0", "date_modified": "7", "guid": "root-guid", "id": "1", "name": "Bookmarks", "type": "folder",
    }

    root = parse_json_item(bookmark_json)
    pages = list(visit(root))

    assert root.name == "Bookmarks"
    assert len(pages) == 2
    assert pages[0].parent is root
    assert pages[1].parent.name == "Nested folder"
    assert pages[1].path.parts[-2:] == ("Nested folder", "Nested")


def test_parser_preserves_nonzero_ids_and_does_not_mutate_payload():
    payload = {"children": [], "date_added": "7", "date_last_used": "0", "date_modified": "7", "guid": "root-guid", "id": "42", "name": "Bookmarks", "type": "folder"}
    root = parse_json_item(payload)
    assert root.id == "42"
    assert "parent" not in payload
    assert "path" not in payload


def test_parser_rejects_unknown_type_with_clear_error():
    with pytest.raises(ValueError, match="Unknown bookmark type: mystery"):
        parse_json_item({"name": "bad", "type": "mystery"})


def test_parser_reports_missing_required_field():
    with pytest.raises(KeyError, match="type"):
        parse_json_item({"name": "bad"})


def test_defaults_are_isolated_between_instances():
    first = BookmarkPage(name="first", url="https://first.example")
    second = BookmarkPage(name="second", url="https://second.example")
    first.meta_info["custom"] = "value"
    first_folder = BookmarkFolder(name="first")
    second_folder = BookmarkFolder(name="second")
    first_folder.children.append(first)
    assert "custom" not in second.meta_info
    assert second_folder.children == []
    assert first.date_added != second.date_added or first.guid != second.guid


def test_page_equality_and_iterator_boundaries_are_safe():
    page = BookmarkPage(name="page", url="https://example.com")
    assert page != object()
    folder = BookmarkFolder(children=[page])
    iterator = folder.get_iterator()
    assert next(iterator) is page
    with pytest.raises(StopIteration):
        next(iterator)
