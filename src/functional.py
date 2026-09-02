# standard library
import json
import time
import uuid
from copy import copy, deepcopy
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
    folder_data = {k: v for k, v in json.items() if k not in ["children", "date_modified"]}
    folder = BookmarkFolder(date_modified=date_modified, **folder_data)
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
    item_data = dict(bmf_json)
    item_data["parent"] = parent
    item_data["path"] = (
        parent.path / item_data["name"].strip() if parent is not None else Path("/")
    )
    # print(bmf_json)
    match item_data["type"]:
        case "folder":
            return parse_json_folder(item_data)
        case "url":
            return parse_json_page(item_data)
        case _:
            raise ValueError(f"Unknown bookmark type: {item_data['type']}")


def _page_key(page: "BookmarkPage") -> tuple[str, str]:
    """以所在目录路径和精确 URL 标识书签。"""
    return str(page.path.parent), page.url


def _time_value(value) -> int:
    """将可转整数的时间转换为排序值，非法值按 0。"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _newer_key(page: "BookmarkPage") -> tuple[int, int]:
    return _time_value(page.date_last_used), _time_value(page.date_added)


def _copy_for_parent(page: "BookmarkPage", parent: "BookmarkFolder") -> "BookmarkPage":
    result = copy_page(page)
    result.parent = parent
    result.path = parent.path / result.name
    return result


def _coalesce_folder(folder: "BookmarkFolder") -> None:
    """在每个目录内收敛重复 URL，并保留较新记录。"""
    # 1. 递归处理子目录，保持目录和页面的原始顺序。
    # 2. 仅在同一父目录中按 URL 合并页面。
    positions = {}
    children = []
    for child in folder.children:
        from src.entity import BookmarkFolder as Folder
        if isinstance(child, Folder):
            _coalesce_folder(child)
            children.append(child)
            continue
        key = child.url
        if key not in positions:
            positions[key] = len(children)
            children.append(child)
        elif _newer_key(child) > _newer_key(children[positions[key]]):
            children[positions[key]] = _copy_for_parent(child, folder)
    folder.children = children

def deduplication(bmf1: "BookmarkFolder", bmf2: "BookmarkFolder") -> list["BookmarkPage"]:
    """返回来源中不在基准同目录的 URL，并按来源顺序保留较新记录。"""
    seen = {_page_key(page): page for page in visit(bmf1)}
    positions = {}
    result = []
    for page in visit(bmf2):
        key = _page_key(page)
        if key not in seen:
            seen[key] = page
            positions[key] = len(result)
            result.append(page)
        elif key in positions and _newer_key(page) > _newer_key(seen[key]):
            seen[key] = page
            result[positions[key]] = page
    return result

def copy_page(page: "BookmarkPage") -> "BookmarkPage":
    """复制页面本身及其可变元数据，不复制来源树的 parent。"""
    result = copy(page)
    result.meta_info = deepcopy(page.meta_info)
    return result


def merge_two(bmf1: "BookmarkFolder", bmf2: "BookmarkFolder") -> "BookmarkFolder":
    """合并两个书签树并返回独立结果。"""
    return merge(bmf1, bmf2)


def merge(*bmfs: Tuple["BookmarkFolder"]) -> "BookmarkFolder":
    """合并书签，按目录路径和 URL 去重，并以较新记录替换冲突。"""
    if not bmfs:
        raise ValueError("merge requires at least one bookmark tree")
    # 1. 复制并收敛基准树自身的目录内冲突。
    # 2. 依次处理来源，保持新增顺序并替换较旧记录。
    res = deepcopy(bmfs[0])
    _coalesce_folder(res)
    index = {_page_key(page): page for page in visit(res)}
    for source in bmfs[1:]:
        for page in visit(source):
            key = _page_key(page)
            current = index.get(key)
            if current is None:
                new_page = copy_page(page)
                res.insert(new_page)
                index[key] = new_page
            elif _newer_key(page) > _newer_key(current):
                replacement = _copy_for_parent(page, current.parent)
                children = current.parent.children
                children[children.index(current)] = replacement
                index[key] = replacement
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
    paths = [parent.stem for parent in bmp.path.parents]
    # 去除开头的根目录，和书签名
    paths = paths[:-1]
    paths.reverse()
    # 查找现有目录
    root_bmf = bmf
    for idx, path in enumerate(paths):
        # 找到存在的目录
        for base in root_bmf.children:
            if base.name == path:
                root_bmf = base
                break
        else:
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


def visit(bmf: "BookmarkFolder") -> Generator["BookmarkPage", None, None]:
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