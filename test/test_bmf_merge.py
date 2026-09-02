import pytest

from src.functional import deduplication, merge, merge_two, parse_json_item, visit


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


def test_merge_is_stable_and_does_not_modify_inputs():
    first = parse_json_item(_folder("Bookmarks", [_page("Base", "https://base.example")]))
    second = parse_json_item(_folder("Bookmarks", [_page("B", "https://b.example"), _page("A", "https://a.example")]))
    before = [page.url for page in visit(first)]
    merged = merge(first, second)
    assert [page.url for page in visit(merged)] == before + ["https://b.example", "https://a.example"]
    assert [page.url for page in visit(first)] == before
    assert [page.url for page in visit(second)] == ["https://b.example", "https://a.example"]
    assert merged is not first


def test_merge_single_input_returns_independent_copy():
    source = parse_json_item(_folder("Bookmarks", [_page("A", "https://a.example")]))
    result = merge(source)
    result.children.clear()
    assert [page.url for page in visit(source)] == ["https://a.example"]


def test_merge_requires_at_least_one_input():
    with pytest.raises(ValueError, match="at least one"):
        merge()


def test_duplicate_urls_are_skipped_but_base_tree_is_preserved():
    base = parse_json_item(_folder("Bookmarks", [_folder("Keep", [_page("Old", "https://same.example")])]))
    later = parse_json_item(_folder("Bookmarks", [_page("Same", "https://same.example")]))
    merged = merge(base, later)
    assert [page.name for page in visit(merged)] == ["Old"]
    assert merged.children[0].name == "Keep"


def test_source_duplicates_are_returned_once_in_order_and_pages_are_isolated():
    base = parse_json_item(_folder("Bookmarks", []))
    source = parse_json_item(_folder("Bookmarks", [_page("A", "https://a.example"), _page("A copy", "https://a.example")]))
    source.children[0].meta_info["source"] = "original"
    unique = deduplication(base, source)
    assert [page.url for page in unique] == ["https://a.example"]
    merged = merge(base, source)
    result_page = next(visit(merged))
    assert result_page is not source.children[0]
    assert result_page.meta_info is not source.children[0].meta_info
    assert result_page.parent is merged


def test_empty_directories_can_be_parsed_and_merged():
    empty = parse_json_item(_folder("Empty", []))
    merged = merge(empty, parse_json_item(_folder("Other", [])))
    assert merged.children == []


def test_same_named_directories_are_reused_when_inserting():
    base = parse_json_item(_folder("Bookmarks", [_folder("Work", [])]))
    source = parse_json_item(_folder("Bookmarks", [_folder("Work", [_page("A", "https://a.example")])]))
    merged = merge(base, source)
    assert [child.name for child in merged.children] == ["Work"]
    assert [page.url for page in visit(merged.children[0])] == ["https://a.example"]
