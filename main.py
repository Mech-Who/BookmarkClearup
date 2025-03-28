"""
Author: HuShuhan 873933169@qq.com
Date: 2025-03-14 16:59:32
LastEditors: hushuhan 873933169@qq.com
LastEditTime: 2025-03-17 19:42:56
FilePath: \BookmarkClearup\main.py
Description: 参考自：https://blog.csdn.net/geoker/article/details/131030675，目标是合并不同浏览器的书签，并且不需要太多手动操作。
"""

# standard library
import logging
import sys
from datetime import datetime
from pathlib import Path

# user custom
from src.constant import DefaultBookmarkPath as DBPath
from src.entity import BookmarkFolder
from src.functional import merge

logger = logging.getLogger(__name__)


def setup_log(log_filename: str = None) -> None:
    """
    description: 配置日志设置
    param log_filename {str}: 日志文件名，自动添加后缀'.log'，默认为'日期_时间'，例如'20250315_122000'
    return {*}
    """
    # log config
    if log_filename is None:
        log_filename = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = Path(f"./logs/{log_filename}.log")
    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[
            logging.FileHandler(filename=str(log_path)),
            logging.StreamHandler(stream=sys.stdout),
        ],
    )


def main():
    setup_log()
    logger.info("Hello from bookmarkclearup!")
    """1. 项目文件测试"""
    # * 书签文件读取
    # bm_dir = Path("./bookmarks")
    # bm_filenames = ["chrome_Bookmarks", "edge_Bookmarks"] # json格式
    # # * 书签文件转换
    # #   * 定义记录书签内容的数据结构
    # #   * 书签文件结构解析
    # #   * 书签文件结构提取
    # #   * 书签内容提取
    # bmfs = [BookmarkFolder.parse_json(bm_dir / file) for file in bm_filenames]
    # # * 书签内容合并
    # #   * 确定书签内容的等价性
    # #   * 书签内容的重复项过滤
    # bm_merge = merge(*bmfs)
    # #   * 书签内容保存
    # #     * 书签内容持久化
    # #     * 书签内容缓存
    # output_dir = Path("./output")
    # filename = "merged.json"
    # # * 书签文件还原
    # #   * 书签内容以书签文件结构进行书签文件的构造
    # bm_merge.dump_json(str(bm_dir / bm_filenames[0]))
    """2. 本地文件测试"""
    chrome_bmf = BookmarkFolder.parse_json(DBPath.CHROME)
    edge_bmf = BookmarkFolder.parse_json(DBPath.EDGE)
    merge_bmf = merge(chrome_bmf, edge_bmf)
    # print(merge_bmf, type(merge_bmf), len(merge_bmf))
    merge_bmf.dump_json(DBPath.CHROME)


if __name__ == "__main__":
    # main
    main()
