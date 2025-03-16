'''
Author: HuShuhan 873933169@qq.com
Date: 2025-03-14 16:59:32
LastEditors: hushuhan 873933169@qq.com
LastEditTime: 2025-03-16 17:17:03
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
from src.entity import BookmarkPage, BookmarkFolder
from src.functional import merge


logger = logging.getLogger(__name__)


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


def main():
    setup_log()
    logger.info("Hello from bookmarkclearup!")
    # * 书签文件读取
    bm_dir = Path("./bookmarks")
    bm_files = ["chrome_Bookmarks", "edge_Bookmarks"] # json格式
    # * 书签文件转换
    #   * 定义记录书签内容的数据结构
    #   * 书签文件结构解析
    #   * 书签文件结构提取
    #   * 书签内容提取
    bm_files = [BookmarkFolder.parse_json(bm_dir / file) for file in bm_files]
    # * 书签内容合并
    #   * 确定书签内容的等价性
    #   * 书签内容的重复项过滤
    bm_merge = merge(*bm_files)
    #   * 书签内容保存
    #     * 书签内容持久化
    #     * 书签内容缓存
    output_dir = Path("./output")
    filename = "merged.json"
    # * 书签文件还原
    #   * 书签内容以书签文件结构进行书签文件的构造
    bm_merge.dump_json(str(output_dir / filename))


if __name__ == "__main__":
    # main
    main()
