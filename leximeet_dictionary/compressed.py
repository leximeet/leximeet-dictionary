"""大词卡流式读写；固定压缩参数，不把整个词典解压到内存。"""

from __future__ import annotations

import io
import json
from contextlib import contextmanager
from pathlib import Path

import zstandard as zstd

from .builder import canonical

COMPRESSION = {"format": "zstd", "python_zstandard": "0.25.0",
               "zstd_version": "1.5.7", "level": 9, "threads": 0,
               "checksum": True, "content_size": False}


def check_compressor() -> None:
    """构建时拒绝浮动工具版本；消费端只需兼容标准 Zstandard 帧。"""
    if (zstd.__version__ != COMPRESSION["python_zstandard"]
            or ".".join(map(str, zstd.ZSTD_VERSION)) != COMPRESSION["zstd_version"]):
        raise ValueError("压缩工具不符合固定版本，请安装 requirements.txt")


@contextmanager
def writer(path: Path):
    """单线程、固定窗口参数与校验和，排除时间戳和文件名等平台差异。"""
    check_compressor()
    with path.open("wb") as raw:
        compressor = zstd.ZstdCompressor(level=COMPRESSION["level"], threads=0,
                                         write_checksum=True, write_content_size=False)
        with compressor.stream_writer(raw, closefd=False) as target:
            yield target


def json_lines(path: Path):
    """一次解析一条记录；帧校验失败会直接报错，不能安装部分词包。"""
    with path.open("rb") as raw:
        with zstd.ZstdDecompressor().stream_reader(raw) as reader:
            with io.TextIOWrapper(reader, encoding="utf-8") as text:
                for line in text:
                    yield json.loads(line)


def write_record(stream, value: dict) -> None:
    stream.write((canonical(value) + "\n").encode("utf-8"))
