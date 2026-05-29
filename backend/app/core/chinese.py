"""
中文繁简转换工具，用于客户搜索时的模糊匹配。
"""
from opencc import OpenCC

_t2s = OpenCC("t2s")  # 繁体 → 简体
_s2t = OpenCC("s2t")  # 简体 → 繁体


def to_simplified(text: str) -> str:
    return _t2s.convert(text)


def to_traditional(text: str) -> str:
    return _s2t.convert(text)


def search_variants(text: str) -> list[str]:
    """生成搜索变体列表（原文 + 简体 + 繁体），去重。"""
    return list(set([text, _t2s.convert(text), _s2t.convert(text)]))
