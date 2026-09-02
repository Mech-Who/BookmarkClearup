from src.functional import merge_two, parse_json_item, visit


def _folder(name, children):
    """Create a minimal in-memory bookmark folder payload."""
    return {"children": children, "date_added": "1", "date_last_used": "0", "date_modified": "1", "guid": f"{name}-guid", "id": "1", "name": name, "type": "folder"}


def _page(name, url):
    """Create a minimal in-memory bookmark page payload."""
    return {"date_added": "1", "date_last_used": "0", "guid": f"{name}-guid", "id": "2", "name": name, "type": "url", "url": url}


def test_merge_two_adds_only_pages_with_new_urls():
    first = parse_json_item(_folder("Bookmarks", [_page("Existing", "https://example.com")]))
    second = parse_json_item(_folder("Bookmarks", [_page("Existing copy", "https://example.com"), _page("New", "https://new.example.com")]))

    merged = merge_two(first, second)

    assert [page.url for page in visit(merged)] == ["https://example.com", "https://new.example.com"]
