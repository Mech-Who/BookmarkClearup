# standard library
import json
import shutil
import time
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Sequence

# third-party
from lxml import etree

from src.constant import DefaultBookmarkPath as DBPath
from src.functional import dump_html, dump_json_folder, insert, merge, parse_json_item

# user custom
from src.metaclasses import LoggerMeta

"""
组合模式: CompositePattern

BookmarkBase
"date_added": "13372929754360786",
"date_last_used": "0",
"guid": "2ca8530f-92ff-4c54-a528-9f14e38884a9",
"id": "1472",
"name": "会议官网",
"source": "unknown",
"type": "folder", # ["folder", "url"]
"parent": None|BookmarkFolder,
"path": Path("/")

BookmarkPage
"meta_info": { "power_bookmark_meta": "" },
"show_icon": false,
"visit_count": 0
"url": "https://..."

BookmarkFolder
"children": [],
"date_modified": "13372929754360786",
"""


class BookmarkBase(metaclass=LoggerMeta):
    """
    提供书签目录的支持。为后续保留书签的目录结构做准备。
    """

    count_n = 1

    def __init__(
        self,
        *,
        date_added: str = str(int(time.time())),
        date_last_used: str = str(int(time.time())),
        guid: str = str(uuid.uuid4()),
        id: int = count_n,
        name: str = "Unknown",
        source: str = "unknown source",
        type: str = "folder",
        # custom attribution
        parent: "BookmarkBase" = None,
        path: Path = Path("/"),
    ):
        if id:
            self.id = BookmarkBase.count_n
            BookmarkBase.count_n += 1
        else:
            self.id = id
            BookmarkBase.count_n = id + 1
        self.date_added = date_added
        self.date_last_used = date_last_used
        self.guid = guid
        self.name = name
        self.source = source
        self.type = type
        self.parent = parent
        self.path = path

    def __hash__(self):
        return hash(self.path)


# HACK: 尝试使用 TypedDict，对字典类型做检查
class BookmarkPage(BookmarkBase):
    def __init__(
        self,
        *,
        url: str,
        meta_info: dict = {"power_bookmark_meta": ""},
        visit_count: int = 0,
        show_icon: bool = False,
        **kw_args: dict,
    ):
        super().__init__(**kw_args)
        self.url = url
        self.meta_info = meta_info
        self.visit_count = visit_count
        self.show_icon = show_icon

    def __hash__(self):
        return hash(self.url)

    def __eq__(self, page: "BookmarkPage"):
        return page.url == self.url

    def __str__(self):
        return f"[{self.name}]({self.url})<{self.path}>"

    def __repr__(self):
        return str(self)


class BookmarkFolder(BookmarkBase):
    def __init__(
        self,
        *,
        children: Sequence[BookmarkPage] = [],
        date_modified: str = str(int(time.time())),
        **kw_args: dict,
    ):
        self.log.debug(f"other parameter{kw_args}")
        super().__init__(**kw_args)
        self.children = list(children)
        self.date_modified = date_modified

    def __str__(self):
        return self.to_str()
        # return f"{self.name}:{str(self.children)}"

    def __repr__(self):
        return str(self)

    def __len__(self):
        return len(self.children)

    def to_str(self, indent: int = 1):
        """
        自定义控制对象转为字符串
        """
        # format
        next_indent = "\t" * indent
        nxl = "\n{}".format(next_indent)  # move to next line
        fmt = ",\n{}".format(next_indent)  # connect to next line
        # start
        res = "{}:[".format(self.name)
        pages = []
        for item in self.children:
            if isinstance(item, BookmarkPage):
                pages.append(str(item))
            if isinstance(item, BookmarkFolder):
                if len(pages) > 0:
                    res += nxl + fmt.join(pages)
                    pages.clear()
                res += fmt + item.to_str(indent + 1)
        if len(pages) > 0:
            res += nxl + fmt.join(pages)
            pages.clear()
        res += "\n{}],".format("\t" * (indent - 1))
        return res

    def get_iterator(self):
        """迭代器实现遍历"""
        return BookmarkIterator(self)

    def get_yield(self):
        """生成器函数实现遍历"""
        for item in tuple(self.children):
            yield item
        """TODO: To be Check"""
        # for item in tuple(self.children):
        #     if isinstance(item, BookmarkPage):
        #         yield item
        #     elif isinstance(item, BookmarkFolder):
        #         return item.get_yield()
        #     else:
        #         raise TypeError(f"Unknown child type: {type(item)}")

    def append(self, base: BookmarkBase) -> None:
        self.children.append(base)
        self.log.info(f"Add '{base}' as a child.")

    def remove(self, base: BookmarkBase) -> None:
        self.children.remove(base)
        self.log.info(f"Remove '{base}' from children.")

    def insert(self, bmp: BookmarkPage) -> None:
        insert(self, bmp)

    def dump_html(self, save_name: Path | str):
        """将书签记录转换回书签文件(*.html)"""
        dump_html(self, save_name)

    def dump_json(self, save_path: Path | str = DBPath.CHROME) -> None:
        """将书签记录转换回书签文件(*.json)"""
        if not isinstance(save_path, Path):
            save_path = Path(save_path)
        res_json = dump_json_folder(self)
        bmf_json = None
        if save_path.exists():
            shutil.copy(save_path, f"{save_path}.bak")  # 注意备份文件
            with open(save_path, "r", encoding="utf-8") as f:
                bmf_json = json.load(f)
        if (
            bmf_json is not None
            and bmf_json.get("roots")
            and bmf_json.get("roots").get("bookmark_bar")
        ):
            bmf_json["roots"]["bookmark_bar"] = res_json
            with open(str(save_path), "w") as f:
                json.dump(bmf_json, f, indent=4)
        else:
            with open(str(save_path), "w") as f:
                json.dump(res_json, f, indent=4)

    def dumps_json(self):
        return dump_json_folder(self)

    def clone_without_children(self):
        n = deepcopy(self)
        n.children = []
        return n

    def merge(self, bm2: "BookmarkFolder"):
        return merge(self, bm2)

    @staticmethod
    def parse_html(bm_filename: str | Path):
        """
        从 html 文件转换得到 BookmarkFolder
        """
        if isinstance(bm_filename, str):
            bm_filename = Path(bm_filename)
        # 解析html格式
        with open(bm_filename, "r", encoding="utf-8") as f:
            contents = f.read()
        tree = etree.HTML(contents)
        # 找到所有的书签链接
        links = tree.xpath("//a")
        links = [each for each in links]
        links.sort(key=lambda x: x.attrib["href"])
        x = tuple(BookmarkPage(link.text, link.attrib["href"]) for link in links)
        return BookmarkFolder(x)

    @staticmethod
    def parse_json(bm_filename: str | Path = DBPath.CHROME):
        """
        从 json 文件转换得到 BookmarkFolder
        """
        if not isinstance(bm_filename, Path):
            bm_filename = Path(bm_filename)
        # FIXME: 通过内容检查、类型检查增强健壮性
        if not bm_filename.isfile():
            raise FileNotFoundError("")
        # HACK: 尝试 object_hook 参数使用
        with open(bm_filename, "r", encoding="utf-8") as f:
            bmf_json = json.load(f)
        return parse_json_item(bmf_json["roots"]["bookmark_bar"])


class BookmarkIterator(metaclass=LoggerMeta):
    def __init__(self, bm: BookmarkFolder):
        self.bm = tuple(item for item in bm.children)
        self.idx = 0

    def __iter__(self):
        self.log.debug("Get bookmark iterator!")
        return self

    def __next__(self):
        res = self.bm[self.idx]
        self.idx += 1
        return res
