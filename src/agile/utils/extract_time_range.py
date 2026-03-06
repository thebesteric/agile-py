"""
中文/英文时间表达式解析器

核心设计思路：
1. 槽位(Slot)机制：一条语句可匹配多个正则，每个正则负责解析不同的槽位
2. 槽位包含：年、月、日、时、分、秒，以及相对偏移信息
3. 支持多语言：通过 language 参数选择中文/英文正则规则
4. 组合结果：所有槽位解析完成后，组合生成最终的时间或时间段

主要类：
- TimeSlot: 时间槽位类，封装年月日时分秒及相关属性
- SlotParser: 槽位解析器基类
- ChineseSlotParser: 中文槽位解析器
- EnglishSlotParser: 英文槽位解析器
- TimeRangeExtractor: 时间范围提取器主类
"""

import re
import datetime
from abc import ABC, abstractmethod
from calendar import monthrange
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict, Tuple, Any, overload, override

from .log_helper import LogHelper

logger = LogHelper.get_logger()


class Language(Enum):
    """支持的语言枚举"""
    CHINESE = "zh"
    ENGLISH = "en"


class SlotType(Enum):
    """槽位类型枚举"""
    YEAR = "year"
    MONTH = "month"
    DAY = "day"
    HOUR = "hour"
    MINUTE = "minute"
    SECOND = "second"
    WEEKDAY = "weekday"
    QUARTER = "quarter"
    PERIOD = "period"  # 时段：上午、下午等
    RELATIVE = "relative"  # 相对时间：昨天、明天等


class OffsetType(Enum):
    """偏移类型"""
    AGO = "ago"  # 之前
    AFTER = "after"  # 之后
    INNER = "inner"  # 之内
    NEAR = "near"  # 近N时间
    NONE = "none"  # 无偏移


@dataclass
class TimeSlot:
    """时间槽位类，封装时间的各个组件"""

    # 基础时间组件
    year: Optional[int] = None
    month: Optional[int] = None
    day: Optional[int] = None
    hour: Optional[int] = None
    minute: Optional[int] = None
    second: Optional[int] = None

    # 扩展组件
    weekday: Optional[int] = None  # 0-6, 0=周一
    quarter: Optional[int] = None  # 1-4
    period: Optional[str] = None  # 时段名称

    # 相对时间偏移
    offset_value: Optional[int] = None  # 偏移数值
    offset_unit: Optional[str] = None  # 偏移单位: 天/周/月/年/小时/分钟
    offset_type: OffsetType = OffsetType.NONE  # 偏移类型

    # 范围标记
    is_range_start: bool = False
    is_range_end: bool = False

    # 相对日期标记
    relative_day: Optional[str] = None  # 昨天/今天/明天等

    # 周相关
    week_offset: int = 0  # 周偏移: -2=上上周, -1=上周, 0=本周, 1=下周, 2=下下周

    # 置信度
    confidence: float = 1.0

    def has_date(self) -> bool:
        """是否包含日期信息"""
        return any([self.year, self.month, self.day, self.weekday, self.quarter, self.relative_day])

    def has_time(self) -> bool:
        """是否包含时间信息"""
        return any([self.hour is not None, self.minute is not None, self.second is not None, self.period])

    def has_offset(self) -> bool:
        """是否包含偏移信息"""
        return self.offset_type != OffsetType.NONE and self.offset_value is not None

    def merge_with(self, other: 'TimeSlot') -> 'TimeSlot':
        """合并两个槽位，优先使用 other 中的非空值"""
        merged = TimeSlot(
            year=other.year if other.year is not None else self.year,
            month=other.month if other.month is not None else self.month,
            day=other.day if other.day is not None else self.day,
            hour=other.hour if other.hour is not None else self.hour,
            minute=other.minute if other.minute is not None else self.minute,
            second=other.second if other.second is not None else self.second,
            weekday=other.weekday if other.weekday is not None else self.weekday,
            quarter=other.quarter if other.quarter is not None else self.quarter,
            period=other.period if other.period is not None else self.period,
            offset_value=other.offset_value if other.offset_value is not None else self.offset_value,
            offset_unit=other.offset_unit if other.offset_unit is not None else self.offset_unit,
            offset_type=other.offset_type if other.offset_type != OffsetType.NONE else self.offset_type,
            is_range_start=other.is_range_start or self.is_range_start,
            is_range_end=other.is_range_end or self.is_range_end,
            relative_day=other.relative_day if other.relative_day is not None else self.relative_day,
            week_offset=other.week_offset if other.week_offset != 0 else self.week_offset,
            confidence=min(self.confidence, other.confidence)
        )
        return merged


@dataclass
class ParseResult:
    """解析结果类"""
    slot_type: SlotType
    slot: TimeSlot
    matched_text: str
    pattern_name: str
    start_pos: int
    end_pos: int


class SlotParserBase(ABC):
    """槽位解析器基类"""

    # 时段映射（子类实现）
    TIME_PERIOD_MAP: Dict[str, Tuple[int, int, int]] = {}

    # 星期映射（子类实现）
    WEEKDAY_MAP: Dict[str, int] = {}

    # 季度映射（子类实现）
    QUARTER_MAP: Dict[str, Tuple[int, int, int]] = {}

    # 数字映射（子类实现）
    NUM_MAP: Dict[str, int] = {}

    def __init__(self):
        self.patterns: List[Tuple[str, str, SlotType]] = []
        self._compile_patterns()

    @abstractmethod
    def _compile_patterns(self):
        """编译正则表达式模式"""
        pass

    def parse_number(self, num_str: str) -> int:
        """将数字字符串转为整数"""
        if not num_str:
            return 0
        if num_str.isdigit():
            return int(num_str)
        if num_str in self.NUM_MAP:
            return self.NUM_MAP[num_str]
        # 处理十位数
        if '十' in num_str or 'teen' in num_str.lower() or 'ty' in num_str.lower():
            return self._parse_complex_number(num_str)
        return 0

    def _parse_complex_number(self, num_str: str) -> int:
        """解析复杂数字（如：二十三）"""
        # 子类可以覆盖
        return 0

    def parse(self, text: str) -> List[ParseResult]:
        """解析文本，返回所有匹配的槽位结果"""
        results = []
        for pattern, name, slot_type in self.patterns:
            for match in re.finditer(pattern, text):
                slot = self._extract_slot(match, name, slot_type)
                if slot:
                    results.append(ParseResult(
                        slot_type=slot_type,
                        slot=slot,
                        matched_text=match.group(0),
                        pattern_name=name,
                        start_pos=match.start(),
                        end_pos=match.end()
                    ))
        return results

    @abstractmethod
    def _extract_slot(self, match: re.Match, pattern_name: str, slot_type: SlotType) -> Optional[TimeSlot]:
        """从匹配结果中提取槽位"""
        pass


class ChineseSlotParser(SlotParserBase):
    """中文槽位解析器"""

    TIME_PERIOD_MAP = {
        '凌晨': (0, 4, 59),
        '清晨': (5, 6, 59),
        '早上': (7, 8, 59),
        '上午': (9, 11, 59),
        '中午': (12, 13, 59),
        '下午': (14, 17, 59),
        '傍晚': (18, 18, 59),
        '晚上': (19, 23, 59)
    }

    WEEKDAY_MAP = {
        '一': 0, '二': 1, '三': 2, '四': 3, '五': 4, '六': 5, '日': 6, '天': 6
    }

    QUARTER_MAP = {
        '1': (1, 1, 3), '一': (1, 1, 3), '第一': (1, 1, 3),
        '2': (2, 4, 6), '二': (2, 4, 6), '第二': (2, 4, 6),
        '3': (3, 7, 9), '三': (3, 7, 9), '第三': (3, 7, 9),
        '4': (4, 10, 12), '四': (4, 10, 12), '第四': (4, 10, 12),
        'q1': (1, 1, 3), 'q2': (2, 4, 6), 'q3': (3, 7, 9), 'q4': (4, 10, 12),
        'Q1': (1, 1, 3), 'Q2': (2, 4, 6), 'Q3': (3, 7, 9), 'Q4': (4, 10, 12)
    }

    NUM_MAP = {
        '零': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5,
        '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
        '十一': 11, '十二': 12
    }

    RELATIVE_DAY_MAP = {
        '大前天': -3, '前天': -2, '昨天': -1, '昨日': -1,
        '今天': 0, '今日': 0, '当天': 0,
        '明天': 1, '明日': 1, '后天': 2, '大后天': 3
    }

    RELATIVE_YEAR_MAP = {
        '前年': -2, '去年': -1, '今年': 0, '本年': 0, '本年度': 0,
        '明年': 1, '来年': 1, '后年': 2
    }

    RELATIVE_MONTH_MAP = {
        '上个月': -1, '上月': -1, '本月': 0, '这个月': 0,
        '下个月': 1, '下月': 1
    }

    RELATIVE_WEEK_MAP = {
        '上上周': -2, '上上个周': -2, '上上星期': -2, '上上个星期': -2, '上上礼拜': -2,
        '上周': -1, '上个周': -1, '上星期': -1, '上个星期': -1, '上礼拜': -1, '上个礼拜': -1,
        '本周': 0, '这周': 0, '这个周': 0, '这星期': 0, '这个星期': 0, '本星期': 0, '这个礼拜': 0, '本礼拜': 0,
        '下周': 1, '下个周': 1, '下星期': 1, '下个星期': 1, '下礼拜': 1, '下个礼拜': 1,
        '下下周': 2, '下下个周': 2, '下下星期': 2, '下下个星期': 2, '下下礼拜': 2
    }

    def _compile_patterns(self):
        """编译中文正则表达式模式"""
        num_pattern = r'(\d+|零|一|二|两|三|四|五|六|七|八|九|十(?:一|二|三|四|五|六|七|八|九)?)'

        self.patterns = [
            # === 年份槽位 ===
            (r'(\d{4})年', 'specific_year', SlotType.YEAR),
            (r'(前年|去年|今年|本年|本年度|明年|来年|后年)', 'relative_year', SlotType.YEAR),
            (r'(上|下)一年', 'last_next_year', SlotType.YEAR),

            # === 季度槽位 ===
            (r'(\d{4})年(第)?([一二三四1234]|Q[1234]|q[1234])季度', 'specific_quarter_with_year', SlotType.QUARTER),
            (r'(本季|本季度|上季度|下季度|下个季度)', 'relative_quarter', SlotType.QUARTER),
            (r'(第)?([一二三四1234]|Q[1234]|q[1234])季度', 'general_quarter', SlotType.QUARTER),

            # === 月份槽位 ===
            (r'(\d{1,2})月(?!份)?(?!前|后|内)', 'specific_month', SlotType.MONTH),
            (r'(上个月|上月|本月|这个月|下个月|下月)', 'relative_month', SlotType.MONTH),

            # === 日期槽位 ===
            (r'(\d{1,2})[日号]', 'specific_day', SlotType.DAY),
            (r'(大前天|前天|昨天|昨日|今天|今日|当天|明天|明日|后天|大后天)', 'relative_day', SlotType.DAY),

            # === 周/星期槽位 ===
            (r'(上上|下下)(个)?(星期|周|礼拜)([一二三四五六日天])', 'double_relative_weekday', SlotType.WEEKDAY),
            (r'(上上|下下)(个)?(星期|周|礼拜)', 'double_relative_week', SlotType.WEEKDAY),
            (r'(上|下)周末', 'weekend', SlotType.WEEKDAY),
            (r'((上|下|这|本)(个)?)?(星期|周|礼拜)([一二三四五六日天])', 'weekday', SlotType.WEEKDAY),
            (r'(本周|这周|这个周|上周|上个周|下周|下个周|这星期|这个星期|本星期|上星期|上个星期|下星期|下个星期|这个礼拜|本礼拜|上礼拜|上个礼拜|下礼拜|下个礼拜)',
             'relative_week', SlotType.WEEKDAY),

            # === 时间范围槽位 ===
            (r'(下)?(个)?(星期|周)([一二三四五六日天])[到至](下)?(个)?(星期|周)([一二三四五六日天])', 'weekday_range', SlotType.WEEKDAY),

            # === 时段槽位 ===
            (r'(凌晨|清晨|早上|上午|中午|下午|傍晚|晚上)', 'time_period', SlotType.PERIOD),

            # === 时间点槽位 ===
            (f'{num_pattern}(点|时)({num_pattern}分?|半)?', 'time_hm', SlotType.HOUR),
            (r'(\d{1,2}):(\d{2})(?::(\d{2}))?', 'time_colon', SlotType.HOUR),

            # === 时间范围槽位（小时:分钟） ===
            (r'(\d{1,2})(点|时|:)?(\d{0,2})?\s*[到至]\s*(\d{1,2})(点|时|:)?(\d{0,2})?', 'time_range', SlotType.HOUR),

            # === 相对偏移槽位 ===
            (f'{num_pattern}(?:个)?(天|周|月|年)(前)', 'offset_ago', SlotType.RELATIVE),
            (f'{num_pattern}(?:个)?(天|周|月|年)(后)', 'offset_after', SlotType.RELATIVE),
            (f'{num_pattern}(?:个)?(天|周|月|年)(内)', 'offset_inner', SlotType.RELATIVE),
            (f'近{num_pattern}(?:个)?(天|周|月|年)', 'offset_near', SlotType.RELATIVE),
            (f'{num_pattern}(?:个)?(小时|时)(前)', 'hour_offset_ago', SlotType.RELATIVE),
            (f'{num_pattern}(?:个)?(小时|时)(后)', 'hour_offset_after', SlotType.RELATIVE),
            (f'{num_pattern}(分钟|分)(前)', 'minute_offset_ago', SlotType.RELATIVE),
            (f'{num_pattern}(分钟|分)(后)', 'minute_offset_after', SlotType.RELATIVE),

            # === 纯数字+单位（无偏移方向） ===
            (f'{num_pattern}(?:个)?(天|周|月|年)(?!前|后|内)', 'num_unit', SlotType.RELATIVE),
        ]

    def _parse_complex_number(self, num_str: str) -> int:
        """解析复杂中文数字"""
        if not num_str:
            return 0
        if num_str in self.NUM_MAP:
            return self.NUM_MAP[num_str]
        if '十' in num_str:
            parts = num_str.split('十')
            tens = self.NUM_MAP.get(parts[0], 1) if parts[0] else 1
            ones = self.NUM_MAP.get(parts[1], 0) if len(parts) > 1 and parts[1] else 0
            return tens * 10 + ones
        return 0

    def parse_number(self, num_str: str) -> int:
        """将数字字符串转为整数"""
        if not num_str:
            return 0
        if num_str.isdigit():
            return int(num_str)
        if num_str in self.NUM_MAP:
            return self.NUM_MAP[num_str]
        return self._parse_complex_number(num_str)

    @override
    def _extract_slot(self, match: re.Match, pattern_name: str, slot_type: SlotType) -> Optional[TimeSlot]:
        """从匹配结果中提取槽位"""
        slot = TimeSlot()
        groups = match.groups()

        try:
            if pattern_name == 'specific_year':
                slot.year = int(groups[0])

            elif pattern_name == 'relative_year':
                offset = self.RELATIVE_YEAR_MAP.get(groups[0], 0)
                slot.offset_value = abs(offset)
                slot.offset_unit = '年'
                slot.offset_type = OffsetType.AGO if offset < 0 else (OffsetType.AFTER if offset > 0 else OffsetType.NONE)
                if offset == 0:
                    slot.relative_day = '今年'

            elif pattern_name == 'last_next_year':
                slot.offset_value = 1
                slot.offset_unit = '年'
                slot.offset_type = OffsetType.AGO if groups[0] == '上' else OffsetType.AFTER

            elif pattern_name == 'specific_quarter_with_year':
                slot.year = int(groups[0])
                q_key = groups[2].lower()
                if q_key in self.QUARTER_MAP:
                    slot.quarter = self.QUARTER_MAP[q_key][0]

            elif pattern_name == 'relative_quarter':
                word = groups[0]
                if word in ['本季', '本季度']:
                    slot.quarter = 0  # 特殊标记：当前季度
                    slot.relative_day = '本季'
                elif word == '上季度':
                    slot.offset_value = 1
                    slot.offset_unit = '季度'
                    slot.offset_type = OffsetType.AGO
                elif word in ['下季度', '下个季度']:
                    slot.offset_value = 1
                    slot.offset_unit = '季度'
                    slot.offset_type = OffsetType.AFTER

            elif pattern_name == 'general_quarter':
                q_key = groups[1].lower() if groups[1] else groups[0].lower()
                if q_key in self.QUARTER_MAP:
                    slot.quarter = self.QUARTER_MAP[q_key][0]

            elif pattern_name == 'specific_month':
                slot.month = int(groups[0])

            elif pattern_name == 'relative_month':
                offset = self.RELATIVE_MONTH_MAP.get(groups[0], 0)
                if offset == 0:
                    slot.relative_day = '本月'
                else:
                    slot.offset_value = abs(offset)
                    slot.offset_unit = '月'
                    slot.offset_type = OffsetType.AGO if offset < 0 else OffsetType.AFTER

            elif pattern_name == 'specific_day':
                slot.day = int(groups[0])

            elif pattern_name == 'relative_day':
                slot.relative_day = groups[0]

            elif pattern_name == 'double_relative_weekday':
                direction = groups[0]
                weekday_char = groups[3]
                slot.weekday = self.WEEKDAY_MAP.get(weekday_char, 0)
                slot.week_offset = -2 if direction == '上上' else 2

            elif pattern_name == 'double_relative_week':
                direction = groups[0]
                slot.week_offset = -2 if direction == '上上' else 2
                slot.is_range_start = True

            elif pattern_name == 'weekend':
                direction = groups[0]
                slot.weekday = 5  # 周六开始
                slot.is_range_start = True
                slot.week_offset = -1 if direction == '上' else 1

            elif pattern_name == 'weekday':
                prefix = groups[1] if groups[1] else ''
                weekday_char = groups[4]
                slot.weekday = self.WEEKDAY_MAP.get(weekday_char, 0)
                if '上' in prefix:
                    slot.week_offset = -1
                elif '下' in prefix:
                    slot.week_offset = 1
                else:
                    slot.week_offset = 0

            elif pattern_name == 'relative_week':
                word = groups[0]
                for key, offset in self.RELATIVE_WEEK_MAP.items():
                    if key == word:
                        slot.week_offset = offset
                        slot.is_range_start = True
                        break

            elif pattern_name == 'weekday_range':
                # 处理星期范围：周一到周五
                is_next = groups[0] is not None
                start_wd = groups[3]
                end_wd = groups[7]
                slot.weekday = self.WEEKDAY_MAP.get(start_wd, 0)
                slot.is_range_start = True
                slot.week_offset = 1 if is_next else 0
                # 创建结束槽位的信息存储在额外属性中
                slot.second = self.WEEKDAY_MAP.get(end_wd, 0)  # 临时存储结束星期

            elif pattern_name == 'time_period':
                slot.period = groups[0]

            elif pattern_name == 'time_hm':
                hour_str = groups[0]
                minute_part = groups[2] if len(groups) > 2 else None
                slot.hour = self.parse_number(hour_str)
                if minute_part == '半':
                    slot.minute = 30
                elif minute_part:
                    cleaned = minute_part.replace('分', '')
                    slot.minute = self.parse_number(cleaned) if cleaned else 0
                else:
                    slot.minute = 0

            elif pattern_name == 'time_colon':
                slot.hour = int(groups[0])
                slot.minute = int(groups[1])
                if groups[2]:
                    slot.second = int(groups[2])

            elif pattern_name == 'time_range':
                # 时间范围
                slot.hour = int(groups[0])
                slot.minute = int(groups[2]) if groups[2] else 0
                slot.is_range_start = True
                # 临时存储结束时间
                slot.second = int(groups[3])  # 结束小时

            elif pattern_name in ['offset_ago', 'offset_after', 'offset_inner']:
                slot.offset_value = self.parse_number(groups[0])
                slot.offset_unit = groups[1]
                if pattern_name == 'offset_ago':
                    slot.offset_type = OffsetType.AGO
                elif pattern_name == 'offset_after':
                    slot.offset_type = OffsetType.AFTER
                else:
                    slot.offset_type = OffsetType.INNER

            elif pattern_name == 'offset_near':
                slot.offset_value = self.parse_number(groups[0])
                slot.offset_unit = groups[1]
                slot.offset_type = OffsetType.NEAR

            elif pattern_name in ['hour_offset_ago', 'hour_offset_after']:
                slot.offset_value = self.parse_number(groups[0])
                slot.offset_unit = '小时'
                slot.offset_type = OffsetType.AGO if 'ago' in pattern_name else OffsetType.AFTER

            elif pattern_name in ['minute_offset_ago', 'minute_offset_after']:
                slot.offset_value = self.parse_number(groups[0])
                slot.offset_unit = '分钟'
                slot.offset_type = OffsetType.AGO if 'ago' in pattern_name else OffsetType.AFTER

            elif pattern_name == 'num_unit':
                slot.offset_value = self.parse_number(groups[0])
                slot.offset_unit = groups[1]
                slot.offset_type = OffsetType.NEAR  # 默认作为近N时间处理

            return slot

        except Exception as e:
            logger.warning(f"解析槽位失败: pattern={pattern_name}, groups={groups}, error={e}")
            return None


class EnglishSlotParser(SlotParserBase):
    """英文槽位解析器"""

    TIME_PERIOD_MAP = {
        'dawn': (0, 4, 59),
        'early morning': (5, 6, 59),
        'morning': (7, 11, 59),
        'noon': (12, 13, 59),
        'afternoon': (14, 17, 59),
        'evening': (18, 20, 59),
        'night': (21, 23, 59)
    }

    WEEKDAY_MAP = {
        'monday': 0, 'mon': 0,
        'tuesday': 1, 'tue': 1, 'tues': 1,
        'wednesday': 2, 'wed': 2,
        'thursday': 3, 'thu': 3, 'thur': 3, 'thurs': 3,
        'friday': 4, 'fri': 4,
        'saturday': 5, 'sat': 5,
        'sunday': 6, 'sun': 6
    }

    QUARTER_MAP = {
        'q1': (1, 1, 3), 'first quarter': (1, 1, 3), '1st quarter': (1, 1, 3),
        'q2': (2, 4, 6), 'second quarter': (2, 4, 6), '2nd quarter': (2, 4, 6),
        'q3': (3, 7, 9), 'third quarter': (3, 7, 9), '3rd quarter': (3, 7, 9),
        'q4': (4, 10, 12), 'fourth quarter': (4, 10, 12), '4th quarter': (4, 10, 12)
    }

    NUM_MAP = {
        'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
        'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
        'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15,
        'sixteen': 16, 'seventeen': 17, 'eighteen': 18, 'nineteen': 19, 'twenty': 20,
        'thirty': 30, 'forty': 40, 'fifty': 50
    }

    RELATIVE_DAY_MAP = {
        'day before yesterday': -2, 'yesterday': -1,
        'today': 0, 'tomorrow': 1, 'day after tomorrow': 2
    }

    def _compile_patterns(self):
        """编译英文正则表达式模式"""
        num_pattern = r'(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)'

        self.patterns = [
            # === 年份槽位 ===
            (r'(\d{4})', 'specific_year', SlotType.YEAR),
            (r'(?i)(last year|this year|next year)', 'relative_year', SlotType.YEAR),

            # === 季度槽位 ===
            (r'(?i)(Q[1-4]|[1-4](?:st|nd|rd|th) quarter)', 'quarter', SlotType.QUARTER),

            # === 月份槽位 ===
            (r'(?i)(january|february|march|april|may|june|july|august|september|october|november|december|'
             r'jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)', 'month_name', SlotType.MONTH),
            (r'(?i)(last month|this month|next month)', 'relative_month', SlotType.MONTH),

            # === 日期槽位 ===
            (r'(\d{1,2})(?:st|nd|rd|th)?(?=\s|,|$)', 'specific_day', SlotType.DAY),
            (r'(?i)(day before yesterday|yesterday|today|tomorrow|day after tomorrow)', 'relative_day', SlotType.DAY),

            # === 周/星期槽位 ===
            (r'(?i)(last|this|next)\s+(week)', 'relative_week', SlotType.WEEKDAY),
            (r'(?i)(last|this|next)?\s*(monday|tuesday|wednesday|thursday|friday|saturday|sunday|'
             r'mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)', 'weekday', SlotType.WEEKDAY),
            (r'(?i)(last|this|next)\s+weekend', 'weekend', SlotType.WEEKDAY),

            # === 时段槽位 ===
            (r'(?i)(dawn|early morning|morning|noon|afternoon|evening|night)', 'time_period', SlotType.PERIOD),

            # === 时间点槽位 ===
            (r'(?i)(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(am|pm)?', 'time_colon', SlotType.HOUR),
            (r'(?i)(\d{1,2})\s*(am|pm|o\'clock)', 'time_simple', SlotType.HOUR),
            (r'(?i)half past (\d{1,2})', 'time_half_past', SlotType.HOUR),
            (r'(\d{1,2}):?(\d{2})?\s*to\s*(\d{1,2}):?(\d{2})?', 'time_range', SlotType.HOUR),

            # === 相对偏移槽位 ===
            (f'(?i){num_pattern}\\s*(days?|weeks?|months?|years?)\\s*ago', 'offset_ago', SlotType.RELATIVE),
            (f'(?i){num_pattern}\\s*(days?|weeks?|months?|years?)\\s*(?:later|from now)', 'offset_after', SlotType.RELATIVE),
            (f'(?i)(?:in|within)\\s*{num_pattern}\\s*(days?|weeks?|months?|years?)', 'offset_inner', SlotType.RELATIVE),
            (f'(?i)(?:last|past|recent)\\s*{num_pattern}\\s*(days?|weeks?|months?|years?)', 'offset_near', SlotType.RELATIVE),
            (f'(?i){num_pattern}\\s*(hours?)\\s*ago', 'hour_offset_ago', SlotType.RELATIVE),
            (f'(?i){num_pattern}\\s*(hours?)\\s*(?:later|from now)', 'hour_offset_after', SlotType.RELATIVE),
            (f'(?i){num_pattern}\\s*(minutes?)\\s*ago', 'minute_offset_ago', SlotType.RELATIVE),
            (f'(?i){num_pattern}\\s*(minutes?)\\s*(?:later|from now)', 'minute_offset_after', SlotType.RELATIVE),
        ]

    @override
    def _extract_slot(self, match: re.Match, pattern_name: str, slot_type: SlotType) -> Optional[TimeSlot]:
        """从匹配结果中提取槽位"""
        slot = TimeSlot()
        groups = match.groups()

        try:
            if pattern_name == 'specific_year':
                slot.year = int(groups[0])

            elif pattern_name == 'relative_year':
                word = groups[0].lower()
                if word == 'last year':
                    slot.offset_value = 1
                    slot.offset_unit = 'year'
                    slot.offset_type = OffsetType.AGO
                elif word == 'next year':
                    slot.offset_value = 1
                    slot.offset_unit = 'year'
                    slot.offset_type = OffsetType.AFTER
                else:
                    slot.relative_day = 'this year'

            elif pattern_name == 'quarter':
                q_str = groups[0].lower()
                for key, val in self.QUARTER_MAP.items():
                    if key in q_str:
                        slot.quarter = val[0]
                        break

            elif pattern_name == 'month_name':
                month_map = {
                    'january': 1, 'jan': 1, 'february': 2, 'feb': 2,
                    'march': 3, 'mar': 3, 'april': 4, 'apr': 4,
                    'may': 5, 'june': 6, 'jun': 6, 'july': 7, 'jul': 7,
                    'august': 8, 'aug': 8, 'september': 9, 'sep': 9,
                    'october': 10, 'oct': 10, 'november': 11, 'nov': 11,
                    'december': 12, 'dec': 12
                }
                slot.month = month_map.get(groups[0].lower(), 1)

            elif pattern_name == 'relative_month':
                word = groups[0].lower()
                if word == 'last month':
                    slot.offset_value = 1
                    slot.offset_unit = 'month'
                    slot.offset_type = OffsetType.AGO
                elif word == 'next month':
                    slot.offset_value = 1
                    slot.offset_unit = 'month'
                    slot.offset_type = OffsetType.AFTER
                else:
                    slot.relative_day = 'this month'

            elif pattern_name == 'specific_day':
                slot.day = int(groups[0])

            elif pattern_name == 'relative_day':
                word = groups[0].lower()
                slot.relative_day = word

            elif pattern_name == 'relative_week':
                prefix = groups[0].lower()
                if prefix == 'last':
                    slot.week_offset = -1
                elif prefix == 'next':
                    slot.week_offset = 1
                else:
                    slot.week_offset = 0
                slot.is_range_start = True

            elif pattern_name == 'weekday':
                prefix = groups[0].lower() if groups[0] else ''
                weekday = groups[1].lower()
                slot.weekday = self.WEEKDAY_MAP.get(weekday, 0)
                if prefix == 'last':
                    slot.week_offset = -1
                elif prefix == 'next':
                    slot.week_offset = 1
                else:
                    slot.week_offset = 0

            elif pattern_name == 'weekend':
                prefix = groups[0].lower()
                slot.weekday = 5  # Saturday
                slot.is_range_start = True
                if prefix == 'last':
                    slot.week_offset = -1
                elif prefix == 'next':
                    slot.week_offset = 1

            elif pattern_name == 'time_period':
                slot.period = groups[0].lower()

            elif pattern_name == 'time_colon':
                slot.hour = int(groups[0])
                slot.minute = int(groups[1])
                if groups[2]:
                    slot.second = int(groups[2])
                if groups[3]:
                    ampm = groups[3].lower()
                    if ampm == 'pm' and slot.hour < 12:
                        slot.hour += 12
                    elif ampm == 'am' and slot.hour == 12:
                        slot.hour = 0

            elif pattern_name == 'time_simple':
                slot.hour = int(groups[0])
                slot.minute = 0
                if groups[1]:
                    ampm = groups[1].lower()
                    if ampm == 'pm' and slot.hour < 12:
                        slot.hour += 12
                    elif ampm == 'am' and slot.hour == 12:
                        slot.hour = 0

            elif pattern_name == 'time_half_past':
                slot.hour = int(groups[0])
                slot.minute = 30

            elif pattern_name == 'time_range':
                slot.hour = int(groups[0])
                slot.minute = int(groups[1]) if groups[1] else 0
                slot.is_range_start = True
                slot.second = int(groups[2])  # 临时存储结束小时

            elif pattern_name in ['offset_ago', 'offset_after', 'offset_inner', 'offset_near']:
                slot.offset_value = self.parse_number(groups[0])
                unit = groups[1].lower().rstrip('s')  # 去掉复数
                slot.offset_unit = unit
                if pattern_name == 'offset_ago':
                    slot.offset_type = OffsetType.AGO
                elif pattern_name == 'offset_after':
                    slot.offset_type = OffsetType.AFTER
                elif pattern_name == 'offset_inner':
                    slot.offset_type = OffsetType.INNER
                else:
                    slot.offset_type = OffsetType.NEAR

            elif pattern_name in ['hour_offset_ago', 'hour_offset_after']:
                slot.offset_value = self.parse_number(groups[0])
                slot.offset_unit = 'hour'
                slot.offset_type = OffsetType.AGO if 'ago' in pattern_name else OffsetType.AFTER

            elif pattern_name in ['minute_offset_ago', 'minute_offset_after']:
                slot.offset_value = self.parse_number(groups[0])
                slot.offset_unit = 'minute'
                slot.offset_type = OffsetType.AGO if 'ago' in pattern_name else OffsetType.AFTER

            return slot

        except Exception as e:
            logger.warning(f"解析槽位失败: pattern={pattern_name}, groups={groups}, error={e}")
            return None


class TimeSlotCombiner:
    """时间槽位组合器，负责将多个槽位组合成最终的时间范围"""

    # 合法时间范围
    MIN_YEAR = 1900
    MAX_YEAR = 2100

    def __init__(self, language: Language = Language.CHINESE):
        self.language = language
        if language == Language.CHINESE:
            self.parser = ChineseSlotParser()
        else:
            self.parser = EnglishSlotParser()

    def combine(self, slots: List[TimeSlot], now: datetime.datetime) -> List[str]:
        """组合槽位，生成最终的时间范围"""
        if not slots:
            return []

        # 合并所有槽位
        merged_slot = TimeSlot()
        for slot in slots:
            merged_slot = merged_slot.merge_with(slot)

        # 根据槽位内容计算时间
        return self._calculate_time_range(merged_slot, now)

    def _calculate_time_range(self, slot: TimeSlot, now: datetime.datetime) -> List[str]:
        """根据槽位计算时间范围"""

        # 处理相对偏移
        if slot.has_offset():
            return self._handle_offset(slot, now)

        # 处理相对日期（昨天、今天、明天等）
        if slot.relative_day:
            return self._handle_relative_day(slot, now)

        # 处理季度
        if slot.quarter is not None:
            return self._handle_quarter(slot, now)

        # 处理周/星期
        if slot.weekday is not None or slot.week_offset != 0 or slot.is_range_start:
            return self._handle_weekday(slot, now)

        # 处理具体日期时间
        return self._handle_specific_datetime(slot, now)

    def _handle_offset(self, slot: TimeSlot, now: datetime.datetime) -> List[str]:
        """处理相对偏移时间"""
        value = slot.offset_value
        unit = slot.offset_unit
        offset_type = slot.offset_type

        # 单位标准化
        unit_map_zh = {'天': 'day', '周': 'week', '月': 'month', '年': 'year', '小时': 'hour', '分钟': 'minute', '季度': 'quarter'}
        unit_map_en = {'day': 'day', 'week': 'week', 'month': 'month', 'year': 'year', 'hour': 'hour', 'minute': 'minute'}
        unit_map = unit_map_zh if self.language == Language.CHINESE else unit_map_en
        std_unit = unit_map.get(unit, unit)

        if std_unit == 'quarter':
            return self._handle_quarter_offset(slot, now)

        if offset_type == OffsetType.AGO:
            return self._calculate_ago(now, value, std_unit)
        elif offset_type == OffsetType.AFTER:
            return self._calculate_after(now, value, std_unit)
        elif offset_type == OffsetType.INNER:
            return self._calculate_inner(now, value, std_unit)
        elif offset_type == OffsetType.NEAR:
            return self._calculate_near(now, value, std_unit)

        return []

    def _calculate_ago(self, now: datetime.datetime, value: int, unit: str) -> List[str]:
        """计算N单位前的时间"""
        value = max(1, min(100, value))

        if unit == 'day':
            target = now - datetime.timedelta(days=value)
            return self._get_day_range(target)
        elif unit == 'week':
            this_monday = now - datetime.timedelta(days=now.weekday())
            target_monday = this_monday - datetime.timedelta(weeks=value)
            target_sunday = target_monday + datetime.timedelta(days=6)
            return [
                target_monday.strftime('%Y-%m-%d 00:00:00'),
                target_sunday.strftime('%Y-%m-%d 23:59:59')
            ]
        elif unit == 'month':
            target = self._add_months(now, -value)
            first_day = datetime.datetime(target.year, target.month, 1)
            last_day = datetime.datetime(target.year, target.month, monthrange(target.year, target.month)[1])
            return [
                first_day.strftime('%Y-%m-%d 00:00:00'),
                last_day.strftime('%Y-%m-%d 23:59:59')
            ]
        elif unit == 'year':
            target_year = now.year - value
            return self._get_year_range(target_year)
        elif unit == 'hour':
            target = now - datetime.timedelta(hours=value)
            return [target.strftime('%Y-%m-%d %H:%M:%S')]
        elif unit == 'minute':
            target = now - datetime.timedelta(minutes=value)
            return [target.strftime('%Y-%m-%d %H:%M:%S')]

        return []

    def _calculate_after(self, now: datetime.datetime, value: int, unit: str) -> List[str]:
        """计算N单位后的时间"""
        value = max(1, min(100, value))

        if unit == 'day':
            target = now + datetime.timedelta(days=value)
            return self._get_day_range(target)
        elif unit == 'week':
            this_monday = now - datetime.timedelta(days=now.weekday())
            target_monday = this_monday + datetime.timedelta(weeks=value)
            target_sunday = target_monday + datetime.timedelta(days=6)
            return [
                target_monday.strftime('%Y-%m-%d 00:00:00'),
                target_sunday.strftime('%Y-%m-%d 23:59:59')
            ]
        elif unit == 'month':
            target = self._add_months(now, value)
            first_day = datetime.datetime(target.year, target.month, 1)
            last_day = datetime.datetime(target.year, target.month, monthrange(target.year, target.month)[1])
            return [
                first_day.strftime('%Y-%m-%d 00:00:00'),
                last_day.strftime('%Y-%m-%d 23:59:59')
            ]
        elif unit == 'year':
            target_year = now.year + value
            return self._get_year_range(target_year)
        elif unit == 'hour':
            target = now + datetime.timedelta(hours=value)
            return [target.strftime('%Y-%m-%d %H:%M:%S')]
        elif unit == 'minute':
            target = now + datetime.timedelta(minutes=value)
            return [target.strftime('%Y-%m-%d %H:%M:%S')]

        return []

    def _calculate_inner(self, now: datetime.datetime, value: int, unit: str) -> List[str]:
        """计算未来N单位内的时间范围"""
        value = max(1, min(100, value))

        if unit == 'day':
            end_dt = now + datetime.timedelta(days=value - 1)
            return [
                now.strftime('%Y-%m-%d 00:00:00'),
                end_dt.strftime('%Y-%m-%d 23:59:59')
            ]
        elif unit == 'week':
            start_monday = now - datetime.timedelta(days=now.weekday())
            end_sunday = start_monday + datetime.timedelta(days=7 * value - 1)
            return [
                start_monday.strftime('%Y-%m-%d 00:00:00'),
                end_sunday.strftime('%Y-%m-%d 23:59:59')
            ]
        elif unit == 'month':
            first = datetime.datetime(now.year, now.month, 1)
            end_dt = self._add_months(now, value - 1)
            last = datetime.datetime(end_dt.year, end_dt.month, monthrange(end_dt.year, end_dt.month)[1])
            return [
                first.strftime('%Y-%m-%d 00:00:00'),
                last.strftime('%Y-%m-%d 23:59:59')
            ]
        elif unit == 'year':
            first = datetime.datetime(now.year, 1, 1)
            last = datetime.datetime(now.year + value - 1, 12, 31)
            return [
                first.strftime('%Y-%m-%d 00:00:00'),
                last.strftime('%Y-%m-%d 23:59:59')
            ]

        return []

    def _calculate_near(self, now: datetime.datetime, value: int, unit: str) -> List[str]:
        """计算近N单位的时间范围"""
        value = max(1, min(100, value))

        if unit == 'day':
            start = now - datetime.timedelta(days=value - 1)
            return [
                start.strftime('%Y-%m-%d 00:00:00'),
                now.strftime('%Y-%m-%d 23:59:59')
            ]
        elif unit == 'week':
            start_monday = now - datetime.timedelta(days=now.weekday() + (value - 1) * 7)
            end_sunday = start_monday + datetime.timedelta(days=7 * value - 1)
            return [
                start_monday.strftime('%Y-%m-%d 00:00:00'),
                end_sunday.strftime('%Y-%m-%d 23:59:59')
            ]
        elif unit == 'month':
            start_dt = self._add_months(now, -(value - 1))
            first = datetime.datetime(start_dt.year, start_dt.month, 1)
            last = datetime.datetime(now.year, now.month, monthrange(now.year, now.month)[1])
            return [
                first.strftime('%Y-%m-%d 00:00:00'),
                last.strftime('%Y-%m-%d 23:59:59')
            ]
        elif unit == 'year':
            start_year = now.year - value + 1
            first = datetime.datetime(start_year, 1, 1)
            last = datetime.datetime(now.year, 12, 31)
            return [
                first.strftime('%Y-%m-%d 00:00:00'),
                last.strftime('%Y-%m-%d 23:59:59')
            ]

        return []

    def _handle_relative_day(self, slot: TimeSlot, now: datetime.datetime) -> List[str]:
        """处理相对日期"""
        relative = slot.relative_day

        # 中文相对日期
        day_offset_zh = {
            '大前天': -3, '前天': -2, '昨天': -1, '昨日': -1,
            '今天': 0, '今日': 0, '当天': 0,
            '明天': 1, '明日': 1, '后天': 2, '大后天': 3
        }
        # 英文相对日期
        day_offset_en = {
            'day before yesterday': -2, 'yesterday': -1,
            'today': 0, 'tomorrow': 1, 'day after tomorrow': 2
        }
        day_offset = day_offset_zh if self.language == Language.CHINESE else day_offset_en

        # 处理相对日期
        if relative in day_offset:
            offset = day_offset[relative]
            target = now + datetime.timedelta(days=offset)

            # 如果有时段信息，返回时段范围
            if slot.period:
                return self._handle_period_time(slot, target)

            # 如果有具体时间，返回时间点
            if slot.hour is not None:
                return self._build_time_point(slot, target)

            return self._get_day_range(target)

        # 处理相对年份
        year_offset_zh = {'今年': 0, '本年': 0, '本年度': 0, '本季': 0}
        year_offset_en = {'this year': 0}
        year_offset = year_offset_zh if self.language == Language.CHINESE else year_offset_en

        if relative in year_offset:
            return self._get_year_range(now.year)

        # 处理相对月份
        month_offset_zh = {'本月': 0, '这个月': 0}
        month_offset_en = {'this month': 0}
        month_offset = month_offset_zh if self.language == Language.CHINESE else month_offset_en

        if relative in month_offset:
            return self._get_month_range(now.year, now.month)

        return []

    def _handle_quarter(self, slot: TimeSlot, now: datetime.datetime) -> List[str]:
        """处理季度"""
        year = slot.year if slot.year else now.year
        quarter = slot.quarter

        # 当前季度
        if quarter == 0:
            quarter = self._get_current_quarter(now)

        return self._get_quarter_range(year, quarter)

    def _handle_quarter_offset(self, slot: TimeSlot, now: datetime.datetime) -> List[str]:
        """处理季度偏移"""
        current_q = self._get_current_quarter(now)
        year = now.year

        if slot.offset_type == OffsetType.AGO:
            if current_q == 1:
                year -= 1
                quarter = 4
            else:
                quarter = current_q - 1
        elif slot.offset_type == OffsetType.AFTER:
            if current_q == 4:
                year += 1
                quarter = 1
            else:
                quarter = current_q + 1
        else:
            quarter = current_q

        return self._get_quarter_range(year, quarter)

    def _handle_weekday(self, slot: TimeSlot, now: datetime.datetime) -> List[str]:
        """处理周/星期"""
        # 处理周末
        if slot.is_range_start and slot.weekday == 5:
            this_sat = self._get_weekday_date(now, 5, 0)
            sat = this_sat + datetime.timedelta(weeks=slot.week_offset)
            sun = sat + datetime.timedelta(days=1)
            return [
                sat.strftime('%Y-%m-%d 00:00:00'),
                sun.strftime('%Y-%m-%d 23:59:59')
            ]

        # 处理整周
        if slot.weekday is None:
            this_monday = now - datetime.timedelta(days=now.weekday())
            target_monday = this_monday + datetime.timedelta(weeks=slot.week_offset)
            target_sunday = target_monday + datetime.timedelta(days=6)
            return [
                target_monday.strftime('%Y-%m-%d 00:00:00'),
                target_sunday.strftime('%Y-%m-%d 23:59:59')
            ]

        # 处理具体星期几
        target = self._get_weekday_date(now, slot.weekday, slot.week_offset)
        return self._get_day_range(target)

    def _handle_specific_datetime(self, slot: TimeSlot, now: datetime.datetime) -> List[str]:
        """处理具体日期时间"""
        year = slot.year if slot.year else now.year
        month = slot.month if slot.month else now.month
        day = slot.day if slot.day else now.day

        # 如果有时段
        if slot.period:
            target = datetime.datetime(year, month, day)
            return self._handle_period_time(slot, target)

        # 如果有具体时间
        if slot.hour is not None:
            target = datetime.datetime(year, month, day)
            return self._build_time_point(slot, target)

        # 只有日期
        if slot.year or slot.month or slot.day:
            target = datetime.datetime(year, month, day)
            return self._get_day_range(target)

        return []

    def _handle_period_time(self, slot: TimeSlot, base_date: datetime.datetime) -> List[str]:
        """处理时段时间"""
        period_map = self.parser.TIME_PERIOD_MAP
        period = slot.period

        if period not in period_map:
            return self._get_day_range(base_date)

        start_hour, end_hour, end_minute = period_map[period]

        # 如果有具体小时，调整为24小时制
        if slot.hour is not None:
            hour = slot.hour
            minute = slot.minute if slot.minute else 0

            # 下午/晚上等时段转换
            if period in ['下午', '傍晚', '晚上', 'afternoon', 'evening', 'night'] and hour < 12:
                hour += 12
            elif period in ['中午', 'noon'] and hour == 0:
                hour = 12

            result_time = datetime.datetime(base_date.year, base_date.month, base_date.day, hour, minute)
            return [result_time.strftime('%Y-%m-%d %H:%M:%S')]

        # 返回时段范围
        start_time = datetime.datetime(base_date.year, base_date.month, base_date.day, start_hour, 0)
        end_time = datetime.datetime(base_date.year, base_date.month, base_date.day, end_hour, end_minute, 59)
        return [
            start_time.strftime('%Y-%m-%d %H:%M'),
            end_time.strftime('%Y-%m-%d %H:%M:%S')
        ]

    def _build_time_point(self, slot: TimeSlot, base_date: datetime.datetime) -> List[str]:
        """构建时间点"""
        hour = slot.hour if slot.hour is not None else 0
        minute = slot.minute if slot.minute is not None else 0
        second = slot.second if slot.second is not None else 0

        # 时段影响
        if slot.period:
            period = slot.period
            if period in ['下午', '傍晚', '晚上', 'afternoon', 'evening', 'night'] and hour < 12:
                hour += 12

        result_time = datetime.datetime(base_date.year, base_date.month, base_date.day, hour, minute, second)
        return [result_time.strftime('%Y-%m-%d %H:%M:%S')]

    def _get_weekday_date(self, now: datetime.datetime, weekday: int, week_offset: int) -> datetime.datetime:
        """获取指定周偏移的某星期几的日期"""
        this_monday = now - datetime.timedelta(days=now.weekday())
        target_monday = this_monday + datetime.timedelta(weeks=week_offset)
        return target_monday + datetime.timedelta(days=weekday)

    def _get_day_range(self, dt: datetime.datetime) -> List[str]:
        """返回单日的时间范围"""
        return [
            dt.strftime('%Y-%m-%d 00:00:00'),
            dt.strftime('%Y-%m-%d 23:59:59')
        ]

    def _get_year_range(self, year: int) -> List[str]:
        """返回年份的时间范围"""
        year = max(self.MIN_YEAR, min(self.MAX_YEAR, year))
        return [
            f'{year}-01-01 00:00:00',
            f'{year}-12-31 23:59:59'
        ]

    def _get_month_range(self, year: int, month: int) -> List[str]:
        """返回月份的时间范围"""
        first = datetime.datetime(year, month, 1)
        last_day = monthrange(year, month)[1]
        last = datetime.datetime(year, month, last_day)
        return [
            first.strftime('%Y-%m-%d 00:00:00'),
            last.strftime('%Y-%m-%d 23:59:59')
        ]

    def _get_quarter_range(self, year: int, quarter: int) -> List[str]:
        """返回季度的时间范围"""
        quarter_months = {1: (1, 3), 2: (4, 6), 3: (7, 9), 4: (10, 12)}
        start_month, end_month = quarter_months[quarter]
        first = datetime.datetime(year, start_month, 1)
        last_day = monthrange(year, end_month)[1]
        last = datetime.datetime(year, end_month, last_day)
        return [
            first.strftime('%Y-%m-%d 00:00:00'),
            last.strftime('%Y-%m-%d 23:59:59')
        ]

    def _get_current_quarter(self, now: datetime.datetime) -> int:
        """获取当前季度"""
        month = now.month
        if month <= 3:
            return 1
        elif month <= 6:
            return 2
        elif month <= 9:
            return 3
        else:
            return 4

    def _add_months(self, dt: datetime.datetime, n: int) -> datetime.datetime:
        """日期增减月份"""
        year = dt.year
        month = dt.month + n
        while month > 12:
            year += 1
            month -= 12
        while month < 1:
            year -= 1
            month += 12
        year = max(self.MIN_YEAR, min(self.MAX_YEAR, year))
        max_day = monthrange(year, month)[1]
        day = min(dt.day, max_day)
        return datetime.datetime(year, month, day, dt.hour, dt.minute, dt.second)


class TimeRangeExtractor:
    """
    时间范围提取器

    核心特性：
    1. 槽位机制：多个正则分别解析不同槽位，然后组合
    2. 多语言支持：通过 language 参数选择中文/英文
    3. 面向对象设计：使用类封装槽位和解析逻辑

    使用示例：
        extractor = TimeRangeExtractor(language='zh')
        result = extractor.extract("明天下午3点开会")
        # ['2026-02-13 15:00:00']
    """

    def __init__(self, language: str = 'zh'):
        """
        初始化提取器

        Args:
            language: 语言选择，'zh' 表示中文，'en' 表示英文
        """
        self.language = Language.CHINESE if language == 'zh' else Language.ENGLISH
        if self.language == Language.CHINESE:
            self.parser = ChineseSlotParser()
        else:
            self.parser = EnglishSlotParser()
        self.combiner = TimeSlotCombiner(self.language)

    def extract(self, text: str, now: datetime.datetime = None) -> List[str]:
        """
        从文本中提取时间范围

        Args:
            text: 输入文本
            now: 当前时间，默认为系统当前时间

        Returns:
            时间范围列表，格式为 ['YYYY-MM-DD HH:MM:SS', 'YYYY-MM-DD HH:MM:SS']
            或单个时间点 ['YYYY-MM-DD HH:MM:SS']
        """
        if not text:
            logger.warning("输入文本为空")
            return []

        if now is None:
            now = datetime.datetime.now()

        # 解析所有槽位
        parse_results = self.parser.parse(text)

        if not parse_results:
            logger.info(f"未匹配到任何时间表达式: {text}")
            return []

        # 按位置排序
        parse_results.sort(key=lambda x: x.start_pos)

        # 去重：过滤重叠的匹配，优先保留更长/更具体的匹配
        parse_results = self._remove_overlapping_matches(parse_results)

        # 日志输出匹配结果
        for result in parse_results:
            logger.debug(f"匹配: pattern={result.pattern_name}, text='{result.matched_text}', slot_type={result.slot_type.value}")

        # 提取所有槽位
        slots = [r.slot for r in parse_results]

        # 组合槽位生成最终结果
        return self.combiner.combine(slots, now)

    def _remove_overlapping_matches(self, results: List[ParseResult]) -> List[ParseResult]:
        """
        去除重叠的匹配结果，优先保留更长/更具体的匹配

        策略：
        1. 如果一个匹配完全包含在另一个匹配中，保留更长的匹配
        2. 如果两个匹配有重叠但不完全包含，都保留
        """
        if len(results) <= 1:
            return results

        # 按匹配长度降序排序，优先处理长匹配
        sorted_results = sorted(results, key=lambda x: -(x.end_pos - x.start_pos))

        kept = []
        for result in sorted_results:
            is_contained = False
            for kept_result in kept:
                # 检查当前结果是否被已保留的结果完全包含
                if (result.start_pos >= kept_result.start_pos and
                        result.end_pos <= kept_result.end_pos):
                    is_contained = True
                    break
            if not is_contained:
                kept.append(result)

        # 恢复原始位置顺序
        kept.sort(key=lambda x: x.start_pos)
        return kept

    def extract_all(self, text: str, now: datetime.datetime = None) -> List[Dict[str, Any]]:
        """
        从文本中提取所有时间表达式的详细信息

        Args:
            text: 输入文本
            now: 当前时间

        Returns:
            包含所有匹配信息的列表
        """
        if not text:
            return []

        if now is None:
            now = datetime.datetime.now()

        parse_results = self.parser.parse(text)

        results = []
        for r in parse_results:
            results.append({
                'matched_text': r.matched_text,
                'pattern_name': r.pattern_name,
                'slot_type': r.slot_type.value,
                'start_pos': r.start_pos,
                'end_pos': r.end_pos,
                'time_range': self.combiner.combine([r.slot], now)
            })

        return results


def extract_time_range(text: str, now: datetime.datetime = None, language: str = 'zh') -> List[str]:
    """
    提取时间范围的快捷函数

    Args:
        text: 输入文本
        now: 当前时间
        language: 语言选择，'zh' 表示中文，'en' 表示英文

    Returns:
        时间范围列表
    """
    extractor = TimeRangeExtractor(language)
    return extractor.extract(text, now)
