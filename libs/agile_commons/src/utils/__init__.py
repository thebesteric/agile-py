# 导出时间范围提取相关模块
from .extract_chinese_time_range import extract_chinese_time_range
from .extract_chinese_time_range_v2 import (
    TimeRangeExtractorV2,
    extract_chinese_time_range_v2,
    TimeSlot,
    SlotType,
    OffsetType,
    Language,
    ChineseSlotParser,
    EnglishSlotParser,
    TimeSlotCombiner,
    ParseResult
)

__all__ = [
    # V1 版本
    'extract_chinese_time_range',
    # V2 版本
    'TimeRangeExtractorV2',
    'extract_chinese_time_range_v2',
    'TimeSlot',
    'SlotType',
    'OffsetType',
    'Language',
    'ChineseSlotParser',
    'EnglishSlotParser',
    'TimeSlotCombiner',
    'ParseResult',
]

