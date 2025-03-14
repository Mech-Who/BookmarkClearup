# standard library
from typing import *
# user custom
from src.metaclasses import LoggerMeta

class BookmarkBase(object):
    """
    提供书签目录的支持。为后续保留书签的目录结构做准备。
    TODO：考虑具体实现细节
    """
    def __init__(self, path: str="/"):
        self.path = path

class Page(object):
    def __init__(self, title: str, url: str):
        self.title = title
        self.url = url

    def __hash__(self):
        return hash(self.url)

    def __eq__(self, page: "Page"):
        return page.url == self.url

    def __str__(self):
        return f"[{self.title}]({self.url})"

    def __repr__(self):
        return str(self)


class Bookmark(object, metaclass=LoggerMeta):
    def __init__(self, page_list: Tuple[Page]=None):
        if page_list:
            self.pages = set(page_list)
        else:
            self.pages = set()

    def __str__(self):
        return str(self.pages)
    def __repr__(self):
        return str(self)
    def __len__(self):
        return len(self.pages)

    def get_iterator(self):
        """迭代器实现遍历"""
        return BookmarkIterator(self)

    def get_yield(self):
        """生成器函数实现遍历"""
        for item in tuple(self.pages):
            yield item

    def append(self, page: Page) -> NoReturn:
        self.pages.add(page)
        self.log.info(f"Add '{page}' to the pages set.")

    def remove(self, page: Page) -> NoReturn:
        self.pages.remove(page)
        self.log.info(f"Remove '{page}' from the pages set.")

    def parse(self):
        """TODO: 将书签文件转换为书签记录进行保存"""
        pass

    def dump(self):
        """TODO: 将书签记录转换回书签文件(*.html)"""
        pass

    def merge(self, bm2: "Bookmark"):
        return self.pages.union(bm2.pages)


class BookmarkIterator(object, metaclass=LoggerMeta):
    def __init__(self, bm: Bookmark):
        self.bm = tuple(item for item in bm.pages)
        self.idx = 0

    def __iter__(self):
        self.log.debug("Get bookmark iterator!")
        return self

    def __next__(self):
        res = self.bm[self.idx]
        self.idx += 1
        return res
