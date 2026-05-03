import json
import re
from pathlib import Path

_FALLBACK_DICT = None


def _load_fallback_dict():
    global _FALLBACK_DICT
    if _FALLBACK_DICT is None:
        dict_path = Path(__file__).parent / 'fallback_t2s.json'
        if dict_path.exists():
            with open(dict_path, 'r', encoding='utf-8') as f:
                _FALLBACK_DICT = json.load(f)
        else:
            _FALLBACK_DICT = {}
    return _FALLBACK_DICT


ZHU_KEEP_COMPOUNDS = [
    '著名', '著作', '著称', '著录', '著者', '著书',
    '专著', '论著', '译著', '原著', '合著', '遗著',
    '显著', '昭著', '卓著', '名著',
]


def traditional_to_simplified(text: str) -> str:
    try:
        from opencc import OpenCC
        cc = OpenCC('t2s')
        return cc.convert(text)
    except ImportError:
        fallback = _load_fallback_dict()
        result = []
        for char in text:
            if char in fallback:
                result.append(fallback[char])
            else:
                result.append(char)
        return ''.join(result)


def convert_zhu_to_zhe(text: str) -> str:
    placeholders = {}
    for i, compound in enumerate(ZHU_KEEP_COMPOUNDS):
        placeholder = f'\x00ZHU{i}\x00'
        placeholders[placeholder] = compound
        text = text.replace(compound, placeholder)
    text = text.replace('著', '着')
    for placeholder, compound in placeholders.items():
        text = text.replace(placeholder, compound)
    return text


def normalize_chinese(text: str) -> str:
    text = traditional_to_simplified(text)
    text = convert_zhu_to_zhe(text)
    return text


def is_traditional_char(char: str) -> bool:
    if len(char) != 1:
        return False
    try:
        from opencc import OpenCC
        cc = OpenCC('t2s')
        return cc.convert(char) != char
    except ImportError:
        return char in _load_fallback_dict()


def _get_traditional_only():
    return _load_fallback_dict()


TRADITIONAL_ONLY = _load_fallback_dict()
