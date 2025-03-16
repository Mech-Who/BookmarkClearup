# standard library
import time
import uuid
from typing import *
from pathlib import Path
from collections import Counter
# user custom
if TYPE_CHECKING:
    from src.entity import BookmarkPage, BookmarkBase, BookmarkFolder


def parse_json_folder(json: dict) -> "BookmarkFolder":
    from src.entity import BookmarkFolder
    children = json["children"]
    date_modified = json["date_modified"]
    json = {k: v for k, v in json.items() if k not in["children", "date_modified"]}
    folder = BookmarkFolder(
        date_modified=date_modified,
        **json
    )
    children_list = []
    for item in children:
        children_list.append(parse_json_item(item, parent=folder))
    folder.children = children_list
    return folder


def parse_json_page(json: dict) -> "BookmarkPage":
    from src.entity import BookmarkPage
    return BookmarkPage(**json)


def parse_json_item(bmf_json: dict, parent: "BookmarkBase"=None) -> "BookmarkFolder":
    """
    将 json 格式的书签信息转化为 BookmarkFolder 对象
    """
    bmf_json["parent"] = parent
    bmf_json["path"] = parent.path / bmf_json['name'].strip() if parent is not None else Path("/")
    # print(bmf_json)
    match bmf_json["type"]:
        case "folder":
            return parse_json_folder(bmf_json)
        case "url":
            return parse_json_page(bmf_json)
        case _:
            TypeError(f"Unknown type of data: {bmf_json['type']}")


def deduplication(bmf1: "BookmarkFolder", bmf2: "BookmarkFolder") -> "BookmarkPage":
    bmf1 = set([item for item in visit(bmf1)])
    bmf2 = set([item for item in visit(bmf2)])
    return list(bmf2 - bmf1)


def merge_two(bmf1: "BookmarkFolder", bmf2: "BookmarkFolder") -> "BookmarkFolder":
    """
    TODO: 实现两个BookmarkFolder的合并
    """
    from src.entity import BookmarkFolder
    # 去重
    bmps = deduplication(bmf1, bmf2)
    # 插入新书签
    ## 没有新书签
    if len(bmps) == 0:
        return bmf1
    print(f"new bookmars count: {len(bmps)}")
    from pprint import pprint
    pprint(bmps)
    ## 有新书签
    for bmp in bmps:
        bmf1.insert(bmp)
    return bmf1


def merge(*bmfs: Tuple["BookmarkFolder"]) -> "BookmarkFolder":
    """
    实现多个BookmarkFolder的合并
    """
    res = bmfs[0]
    for i in range(1, len(bmfs)):
        res = merge_two(res, bmfs[i])
    return res


def insert(bmf: "BookmarkFolder", bmp: "BookmarkPage") -> NoReturn:
    # 获得所有中间目录名
    print(f"{'='*10}[Insert bookmarkpage]{'='*10}")
    print(f"New item's path: {bmp.path}")
    paths = [parent.stem for parent in bmp.path.parents]
    # 去除开头的根目录，和书签名
    paths = paths[:-1]
    paths.reverse()
    print(f"paths: {paths}")
    # 查找现有书签
    root_bmf = bmf
    for idx, path in enumerate(paths):
        # 找到存在的目录
        for base in root_bmf.children:
            if base.name == path:
                print(f"Dir found: {path}")
                root_bmf = base
                break
        else:
            print(f"Dir not found: '{path}'")
            # 没有该目录
            timestamp = str(int(time.time()))
            dir_path = list(bmp.path.parents)[-1-idx]
            bmf_dir = BookmarkFolder(name=path,
                                    path=dir_path,
                                    parent=root_bmf,
                                    type="folder",
                                    source="unknown",
                                    guid=uuid.uuid4(),
                                    date_modified=timestamp,
                                    date_added=timestamp,
                                    date_last_used=timestamp)
            root_bmf.append(bmf_dir)
            root_bmf = bmf_dir
    bmp.parent = root_bmf
    root_bmf.append(bmp)
    print(f"{'='*10}[Insert finished]{'='*10}")


def dump_html(bmf: "BookmarkFolder", save_name: Path|str) -> NoReturn:
    """
    TODO: 将书签记录转换回书签文件(*.html)
    """
    raise NotImplementedError("src.functional.dump_html 尚未实现！")


def dump_json(bmf: "BookmarkFolder", save_name: Path|str) -> NoReturn:
    """
    TODO: 将书签记录转换回书签文件(Bookmarks, 即json格式文件)
    """
    raise NotImplementedError("src.functional.dump_json 尚未实现！")


def visit(bmf: "BookmarkFolder") -> Generator:
    """
    实现一个for循环遍历所有标签
    """
    from src.entity import BookmarkPage, BookmarkFolder
    for i in bmf.get_yield():
        if isinstance(i, BookmarkPage):
            yield i
        elif isinstance(i, BookmarkFolder):
            # TODO: check yield from 用法
            yield from visit(i)
        else:
            raise TypeError(f"Unknown type: {type(i)}")
