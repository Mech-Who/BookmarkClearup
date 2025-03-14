'''
Author: HuShuhan 873933169@qq.com
Date: 2025-03-14 16:59:32
LastEditors: HuShuhan 873933169@qq.com
LastEditTime: 2025-03-14 17:01:43
FilePath: \BookmarkClearup\main.py
Description: 参考自：https://blog.csdn.net/geoker/article/details/131030675，目标是合并不同浏览器的书签，并且不需要太多手动操作。
'''
# standard library
from pathlib import Path
from typing import *
# third-party
import requests
from lxml import etree

class Page(object):
    def __init__(self, title, url):
        self.title = title
        self.url = url

    def __eq__(self, page: "Page"):
        return page.url == self.url


class Bookmark(object):
    def __init__(self, page_list: List[Page]):
        self.pages = set(page_list)

    def append(self, page: Page) -> NoReturn:
        self.pages.add(page)

    def remove(self, page: Page) -> NoReturn:
        self.pages.remove(page)

    @property
    def pages(self) -> set:
        return self.pages

    def merge(self, bm2: "Bookmark"):
        return self.pages.union(bm2.pages)



def parse_bookmark(bookmark_path: str, save_filename: str=None, is_save: bool=False) -> List[Page]:
    """
    # @description: 读取导出的书签文件的内容并保存
    # @param {str} bookmark 导出的书签文件路径
    # @param {str} save_filename 转换后的内容保存到的文件名
    # @param {bool} is_save 转换后的内容是否要保存
    # @return {*}
    """
    bookmark_path = Path(bookmark_path)
    # 解析html格式
    with open(bookmark_path, 'r', encoding='utf-8') as f:
        contents = f.read()
    tree = etree.HTML(contents)
    # 找到所有的书签链接
    links = tree.xpath('//a')
    links = [each for each in links]
    links.sort(key=lambda x: x.attrib['href'])
    # 打印每个链接的标题和网址
    print(len(links))
    # x = [f"{link.text}\t{link.attrib['href']}" for link in links]
    x = [Page(link.text, link.attrib['href']) for link in links]
    if is_save:
        if save_filename is None:
            save_filename = bookmark_path.parent / f'{bookmark_path.stem}.txt'
        with open(save_filename, 'w', encoding='utf-8') as f:
            f.write('\n'.join(x.pages()))
    return x


def main():
    print("Hello from bookmarkclearup!")
    bookmark = "bookmarks_2025_3_14.html"
    bookmark2 = "favorites_2025_3_14.html"
    parse_bookmark(bookmark2)


if __name__ == "__main__":
    main()
