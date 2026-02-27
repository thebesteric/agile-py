"""
测试 extract_time_range.py 的单元测试

测试时间范围提取功能，包括：
1. 中文时间表达式解析
2. 英文时间表达式解析
3. 槽位组合功能
4. 边界情况处理
"""

import datetime
import unittest

from libs.agile_commons.src.utils.extract_time_range import (
    TimeRangeExtractor,
    TimeSlot,
    SlotType,
    OffsetType,
    ChineseSlotParser,
    EnglishSlotParser,
    TimeSlotCombiner,
    Language,
    extract_time_range,
)


class TestTimeSlot(unittest.TestCase):
    """测试 TimeSlot 类"""

    def test_has_date(self):
        slot = TimeSlot(year=2026)
        self.assertTrue(slot.has_date())

        slot = TimeSlot(month=2)
        self.assertTrue(slot.has_date())

        slot = TimeSlot(hour=10)
        self.assertFalse(slot.has_date())

    def test_has_time(self):
        slot = TimeSlot(hour=10)
        self.assertTrue(slot.has_time())

        slot = TimeSlot(period='上午')
        self.assertTrue(slot.has_time())

        slot = TimeSlot(year=2026)
        self.assertFalse(slot.has_time())

    def test_has_offset(self):
        slot = TimeSlot(offset_value=3, offset_unit='天', offset_type=OffsetType.AGO)
        self.assertTrue(slot.has_offset())

        slot = TimeSlot(offset_type=OffsetType.NONE)
        self.assertFalse(slot.has_offset())

    def test_merge_with(self):
        slot1 = TimeSlot(year=2026, month=2)
        slot2 = TimeSlot(day=12, hour=10)

        merged = slot1.merge_with(slot2)

        self.assertEqual(merged.year, 2026)
        self.assertEqual(merged.month, 2)
        self.assertEqual(merged.day, 12)
        self.assertEqual(merged.hour, 10)


class TestChineseSlotParser(unittest.TestCase):
    """测试中文槽位解析器"""

    def setUp(self):
        self.parser = ChineseSlotParser()

    def test_parse_number(self):
        self.assertEqual(self.parser.parse_number('5'), 5)
        self.assertEqual(self.parser.parse_number('五'), 5)
        self.assertEqual(self.parser.parse_number('十二'), 12)
        self.assertEqual(self.parser.parse_number('二十三'), 23)

    def test_parse_relative_day(self):
        results = self.parser.parse('昨天我去了北京')
        self.assertTrue(any(r.pattern_name == 'relative_day' for r in results))

    def test_parse_time_period(self):
        results = self.parser.parse('明天下午开会')
        self.assertTrue(any(r.slot.period == '下午' for r in results))

    def test_parse_offset(self):
        results = self.parser.parse('3天前的数据')
        offset_results = [r for r in results if r.slot.offset_type == OffsetType.AGO]
        self.assertTrue(len(offset_results) > 0)


class TestEnglishSlotParser(unittest.TestCase):
    """测试英文槽位解析器"""

    def setUp(self):
        self.parser = EnglishSlotParser()

    def test_parse_relative_day(self):
        results = self.parser.parse('I went to Beijing yesterday')
        self.assertTrue(any(r.pattern_name == 'relative_day' for r in results))

    def test_parse_weekday(self):
        results = self.parser.parse('Meeting on next Monday')
        weekday_results = [r for r in results if r.slot.weekday is not None]
        self.assertTrue(len(weekday_results) > 0)

    def test_parse_time(self):
        results = self.parser.parse('Meeting at 3:30 pm')
        time_results = [r for r in results if r.slot.hour is not None]
        self.assertTrue(len(time_results) > 0)


class TestExtractChineseTimeRangeV2(unittest.TestCase):
    """测试 V2 版本的中文时间提取"""

    def setUp(self):
        self.curr = datetime.datetime(2026, 2, 12, 11, 30)
        self.extractor = TimeRangeExtractor(language='zh')

    def _assert_cases(self, cases):
        for text, expected in cases:
            with self.subTest(text=text):
                result = self.extractor.extract(text, self.curr)
                self.assertEqual(expected, result)

    def test_relative_dates(self):
        """测试相对日期"""
        cases = [
            ("昨天我和你说了什么？", ['2026-02-11 00:00:00', '2026-02-11 23:59:59']),
            ("去年我们去了北京旅游。", ['2025-01-01 00:00:00', '2025-12-31 23:59:59']),
            ("本年度的工作计划是什么？", ['2026-01-01 00:00:00', '2026-12-31 23:59:59']),
            ("下季度计划拓展新业务。", ['2026-04-01 00:00:00', '2026-06-30 23:59:59']),
            ("2026年第三季度要去上海出差。", ['2026-07-01 00:00:00', '2026-09-30 23:59:59']),
            ("五个月前入职的", ['2025-09-01 00:00:00', '2025-09-30 23:59:59']),
        ]
        self._assert_cases(cases)

    def test_week_expressions(self):
        """测试周相关表达式"""
        cases = [
            ("下周五记得提醒我去出差。", ['2026-02-20 00:00:00', '2026-02-20 23:59:59']),
            ("本周五公司团建。", ['2026-02-13 00:00:00', '2026-02-13 23:59:59']),
            ("今天有空，来找我。", ['2026-02-12 00:00:00', '2026-02-12 23:59:59']),
            ("下个星期，一起去钓鱼。", ['2026-02-16 00:00:00', '2026-02-22 23:59:59']),
        ]
        self._assert_cases(cases)

    def test_day_offsets(self):
        """测试天级偏移"""
        cases = [
            ("3天前我们开了个会", ['2026-02-09 00:00:00', '2026-02-09 23:59:59']),
            ("3天后完成任务", ['2026-02-15 00:00:00', '2026-02-15 23:59:59']),
        ]
        self._assert_cases(cases)

    def test_time_points_and_periods(self):
        """测试时间点和时段"""
        cases = [
            ("明天下午一起吃饭。", ['2026-02-13 14:00', '2026-02-13 17:59:59']),
        ]
        self._assert_cases(cases)

    def test_hour_minute_offsets(self):
        """测试小时/分钟偏移"""
        cases = [
            ("1小时前", ['2026-02-12 10:30:00']),
        ]
        self._assert_cases(cases)


class TestExtractEnglishTimeRangeV2(unittest.TestCase):
    """测试 V2 版本的英文时间提取"""

    def setUp(self):
        self.curr = datetime.datetime(2026, 2, 12, 11, 30)
        self.extractor = TimeRangeExtractor(language='en')

    def test_relative_dates(self):
        """测试英文相对日期"""
        result = self.extractor.extract("I went shopping yesterday", self.curr)
        self.assertEqual(result, ['2026-02-11 00:00:00', '2026-02-11 23:59:59'])

    def test_next_week(self):
        """测试下周"""
        result = self.extractor.extract("Meeting next Monday", self.curr)
        self.assertEqual(result, ['2026-02-16 00:00:00', '2026-02-16 23:59:59'])

    def test_days_ago(self):
        """测试N天前"""
        result = self.extractor.extract("3 days ago", self.curr)
        self.assertEqual(result, ['2026-02-09 00:00:00', '2026-02-09 23:59:59'])


class TestExtractFunction(unittest.TestCase):
    """测试兼容函数"""

    def setUp(self):
        self.curr = datetime.datetime(2026, 2, 12, 11, 30)

    def test_chinese(self):
        result = extract_time_range("昨天", self.curr, language='zh')
        self.assertEqual(result, ['2026-02-11 00:00:00', '2026-02-11 23:59:59'])

    def test_english(self):
        result = extract_time_range("yesterday", self.curr, language='en')
        self.assertEqual(result, ['2026-02-11 00:00:00', '2026-02-11 23:59:59'])


if __name__ == "__main__":
    unittest.main()
