'''
Author: HuShuhan 873933169@qq.com
Date: 2025-03-14 16:59:32
LastEditors: hushuhan 873933169@qq.com
LastEditTime: 2025-03-15 01:12:41
FilePath: \BookmarkClearup\main.py
Description: 参考自：https://blog.csdn.net/geoker/article/details/131030675，目标是合并不同浏览器的书签，并且不需要太多手动操作。
'''
# standard library
import sys
import logging
from typing import *
from pathlib import Path
from datetime import datetime
# third-party
from lxml import etree
# user custom
from src.entity import Page, Bookmark
from src.functional import merge


logger = logging.getLogger(__name__)


def parse_bookmark(bookmark_path: str, save_filename: str=None, is_save: bool=False) -> Bookmark:
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
    # 记录每个链接的标题和网址
    x = tuple(Page(link.text, link.attrib['href']) for link in links)
    if is_save:
        if save_filename is None:
            save_filename = bookmark_path.parent / f'{bookmark_path.stem}.txt'
        with open(save_filename, 'w', encoding='utf-8') as f:
            f.write('\n'.join(x))
    return Bookmark(x)


def parse_bookmark_with_folder():
    pass


def main():
    setup_log()
    logger.info("Hello from bookmarkclearup!")
    bookmark1 = "bookmarks/bookmarks_2025_3_14.html"
    bm1 = parse_bookmark(bookmark1)
    # print(bm1)
    bookmark2 = "bookmarks/favorites_2025_3_14.html"
    bm2 = parse_bookmark(bookmark2)
    # count = 0
    # for page in bm1.get_yield():
    #     print(page)
    #     count += 1
    #     if count > 10:
    #         break
    logger.info(f"{len(bm1)=}")
    logger.info(f"{len(bm2)=}")
    # bm3 = bm1.merge(bm2)
    bm3 = merge(bm1, bm2)
    logger.info(f"{len(bm3)=}")


def setup_log(log_filename: str=None) -> NoReturn:
    """
    description: 配置日志设置
    param log_filename {str}: 日志文件名，自动添加后缀'.log'，默认为'日期_时间'，例如'20250315_122000'
    return {*}
    """
    # log config
    if log_filename is None:
        log_filename = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = Path(f"./logs/{log_filename}.log")
    logging.basicConfig(level=logging.DEBUG,
                        handlers=[
                            logging.FileHandler(filename=str(log_path)),
                            logging.StreamHandler(stream=sys.stdout)
                        ])


if __name__ == "__main__":
    # main
    main()
