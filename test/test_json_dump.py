import json
import tempfile
from pathlib import Path

from src.functional import dump_json, parse_json_item


def test_dump_json_writes_bookmark_folder_to_file():
    bookmark_json = {"children": [{"date_added": "1", "date_last_used": "0", "guid": "page-guid", "id": "2", "name": "Example", "type": "url", "url": "https://example.com"}], "date_added": "3", "date_last_used": "0", "date_modified": "3", "guid": "root-guid", "id": "1", "name": "Bookmarks", "type": "folder"}

    with tempfile.TemporaryDirectory(dir=Path("test")) as temp_dir:
        output_path = Path(temp_dir) / "merged.json"
        dump_json(parse_json_item(bookmark_json), output_path)

        dumped = json.loads(output_path.read_text(encoding="utf-8"))
        assert dumped["name"] == "Bookmarks"
        assert dumped["children"][0]["url"] == "https://example.com"
