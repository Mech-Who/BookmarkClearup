# standard library
import json
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Generator, Tuple

# user custom
if TYPE_CHECKING:
    from src.entity import BookmarkBase, BookmarkFolder, BookmarkPage


def parse_json_folder(json: dict) -> "BookmarkFolder":
    """
    将书签目录信息转换为 BookmarkFolder 对象。
    通过递归，实现子层级的解析。
    """
    from src.entity import BookmarkFolder

    children = json["children"]
    date_modified = json["date_modified"]
    json = {k: v for k, v in json.items() if k not in ["children", "date_modified"]}
    folder = BookmarkFolder(date_modified=date_modified, **json)
    children_list = []
    for item in children:
        children_list.append(parse_json_item(item, parent=folder))
    folder.children = children_list
    return folder


def parse_json_page(json: dict) -> "BookmarkPage":
    """
    将 json 格式的书签信息转换为 BookmarkPage 对象
    """
    from src.entity import BookmarkPage

    return BookmarkPage(**json)


def parse_json_item(bmf_json: dict, parent: "BookmarkBase" = None) -> "BookmarkFolder":
    """
    将 json 格式的书签信息转化为 BookmarkFolder 对象
    原理：递归解析
    """
    bmf_json["parent"] = parent
    bmf_json["path"] = (
        parent.path / bmf_json["name"].strip() if parent is not None else Path("/")
    )
    # print(bmf_json)
    match bmf_json["type"]:
        case "folder":
            return parse_json_folder(bmf_json)
        case "url":
            return parse_json_page(bmf_json)
        case _:
            TypeError(f"Unknown type of data: {bmf_json['type']}")


def deduplication(bmf1: "BookmarkFolder", bmf2: "BookmarkFolder") -> "BookmarkPage":
    """
    实现两个 BookmarkFolder 对象间的去重。
    """
    # LEARN: set 的参数是一个 Iterator 即可
    bmf1 = set(visit(bmf1))
    bmf2 = set(visit(bmf2))
    return list(bmf2 - bmf1)


def merge_two(bmf1: "BookmarkFolder", bmf2: "BookmarkFolder") -> "BookmarkFolder":
    """
    实现两个 BookmarkFolder 对象的合并
    """
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
    实现多个BookmarkFolder的合并。
    基于merge_two，实现多个书签文件的合并。
    """
    res = bmfs[0]
    for i in range(1, len(bmfs)):
        res = merge_two(res, bmfs[i])
    return res


def insert(bmf: "BookmarkFolder", bmp: "BookmarkPage") -> None:
    """
    description: 向 BookmarkFolder 对象中添加 BookmarkPage (书签)
    param {*} bmf 要添加书签的 BookmarkFolder 对象
    param {*} bmp 要添加到 BOokmarkFolder 的书签
    return {*}
    """
    from src.entity import BookmarkFolder

    # 获得所有中间目录名
    print(f"{'=' * 10}[Insert bookmarkpage]{'=' * 10}")
    print(f"New item's path: {bmp.path}")
    paths = [parent.stem for parent in bmp.path.parents]
    # 去除开头的根目录，和书签名
    paths = paths[:-1]
    paths.reverse()
    print(f"paths: {paths}")
    # 查找现有目录
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
            # 没有该目录，则创建目录对象
            timestamp = str(int(time.time()))
            dir_path = list(bmp.path.parents)[-1 - idx]
            bmf_dir = BookmarkFolder(
                name=path,
                path=dir_path,
                parent=root_bmf,
                type="folder",
                source="unknown",
                guid=str(uuid.uuid4()),
                date_modified=timestamp,
                date_added=timestamp,
                date_last_used=timestamp,
            )
            root_bmf.append(bmf_dir)
            root_bmf = bmf_dir
    bmp.parent = root_bmf
    root_bmf.append(bmp)
    print(f"{'=' * 10}[Insert finished]{'=' * 10}")


def dump_html(bmf: "BookmarkFolder", save_name: Path | str) -> None:
    """
    TODO: 将书签记录转换回书签文件(*.html)
    """
    raise NotImplementedError("src.functional.dump_html 尚未实现！")


def dump_json_folder(bmf: "BookmarkFolder") -> None:
    from src.entity import BookmarkFolder, BookmarkPage

    # print(bmf.values)
    # print(f"bmf: {type(bmf)}", dir(bmf))
    bmf_dict = {
        "date_added": bmf.date_added,
        "date_last_used": bmf.date_last_used,
        "guid": bmf.guid,
        "id": bmf.id,
        "name": bmf.name,
        "source": bmf.source,
        "type": bmf.type,
        "date_modified": bmf.date_modified,
        "children": [],
    }
    for child in bmf.children:
        child_dict = None
        if isinstance(child, BookmarkFolder):
            child_dict = dump_json_folder(child)
        elif isinstance(child, BookmarkPage):
            child_dict = dump_json_page(child)
        else:
            raise TypeError(f"Unknown type of child: {type(child)}")
        bmf_dict["children"].append(child_dict)
    return bmf_dict


def dump_json_page(bmp: "BookmarkPage") -> None:
    bmp_dict = {
        "date_added": bmp.date_added,
        "date_last_used": bmp.date_last_used,
        "guid": bmp.guid,
        "id": bmp.id,
        "name": bmp.name,
        "source": bmp.source,
        "type": bmp.type,
        "meta_info": bmp.meta_info,
        "show_icon": bmp.show_icon,
        "visit_count": bmp.visit_count,
        "url": bmp.url,
    }
    return bmp_dict


def dump_json(bmf: "BookmarkFolder", save_path: Path | str) -> None:
    """
    将书签记录转换回书签文件(Bookmarks, 即json格式文件)
    """
    bmf_dict = dump_json_folder(bmf)
    with open(str(save_path), "w") as f:
        json.dump(bmf_dict, f, indent=4)


def visit(bmf: "BookmarkFolder") -> Generator["BookmarkPage"]:
    """
    实现一个for循环遍历所有标签
    语法: yield + yield from
    """
    from src.entity import BookmarkFolder, BookmarkPage

    for i in bmf.get_yield():
        if isinstance(i, BookmarkPage):
            yield i
        elif isinstance(i, BookmarkFolder):
            yield from visit(i)
        else:
            raise TypeError(f"Unknown type: {type(i)}")
