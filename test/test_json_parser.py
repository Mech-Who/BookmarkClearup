# standard library
import os
import json
# user custom
from src.functional import parse_json_item, visit


local_appdata_dir = os.environ["LOCALAPPDATA"]
chrome_bmf = rf"{local_appdata_dir}\Google\Chrome\User Data\Default\Bookmarks"
edge_bmf = rf"{local_appdata_dir}\Microsoft\Edge\User Data\Default\Bookmarks"

print(chrome_bmf)
# print(edge_bmf)

with open(chrome_bmf, "r", encoding="utf-8") as f:
    chrome_bf_json = json.load(f)["roots"]["bookmark_bar"]
# print(chrome_bf_json)

bmf = parse_json_item(chrome_bf_json)
# print(bmf.name, bmf.parent, bmf.path, len(bmf.children))

for index, page in enumerate(visit(bmf)):
    print(f"{index}. {page.parent.name} {page.path}")
