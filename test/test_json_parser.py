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
