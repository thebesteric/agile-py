import re
import datetime
from calendar import monthrange
from typing import List, Tuple

from agile_commons.utils.log_helper import LogHelper

logger = LogHelper.get_logger()

# 时段映射
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

# 季度映射
QUARTER_MAP = {
    '1': (1, 1, 3), '一': (1, 1, 3), '第一': (1, 1, 3),
    '2': (2, 4, 6), '二': (2, 4, 6), '第二': (2, 4, 6),
    '3': (3, 7, 9), '三': (3, 7, 9), '第三': (3, 7, 9),
    '4': (4, 10, 12), '四': (4, 10, 12), '第四': (4, 10, 12),
    'q1': (1, 1, 3), 'q2': (2, 4, 6), 'q3': (3, 7, 9), 'q4': (4, 10, 12)
}

# 中文数字转阿拉伯数字映射
CHINESE_NUM_MAP = {
    '零': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5,
    '六': 6, '七': 7, '八': 8, '九': 9, '十': 10
}

# 合法时间范围
MIN_YEAR = 1900
MAX_YEAR = 2100

# 正则规则
PATTERNS = [

    (r'(\d+|零|一|二|两|三|四|五|六|七|八|九|十)(?:个)?(天|周|月|年)前', 'num_time_ago'),  # 过去N天/周/月/年
    (r'(\d+|零|一|二|两|三|四|五|六|七|八|九|十)(?:个)?(天|周|月|年)后', 'num_time_after'),  # 未来N天/周/月/年
    (r'(\d+|零|一|二|两|三|四|五|六|七|八|九|十)(?:个)?(天|周|月|年)内', 'num_time_inner'),  # 未来N天/周/月/年内
    (r'近(\d+|零|一|二|两|三|四|五|六|七|八|九|十)(?:个)?(天|周|月|年)', 'near_num_time'),  # 近N天/周/月/年

    (r'(\d+|零|一|二|两|三|四|五|六|七|八|九|十)(?:个)?(小时|时)前', 'num_hour_ago'),  # 过去N小时
    (r'(\d+|零|一|二|两|三|四|五|六|七|八|九|十)(?:个)?(小时|时)后', 'num_hour_after'),  # 未来N小时
    (r'(\d+|零|一|二|两|三|四|五|六|七|八|九|十)(分钟|分)前', 'num_min_ago'),  # 过去N分钟
    (r'(\d+|零|一|二|两|三|四|五|六|七|八|九|十)(分钟|分)后', 'num_min_after'),  # 未来N分钟

    (r'(下)?(个)?(星期|周)([一二三四五六日天])到(下)?(个)?(星期|周)([一二三四五六日天])', 'time_range_weekday'),  # 星期区间
    (r'下(个)?(星期|周)([一二三四五六日])', 'next_weekday'),  # 下周具体星期几
    (r'下季度|下个季度', 'next_quarter'),  # 下季度范围
    (r'(\d+|零|一|二|两|三|四|五|六|七|八|九|十)(?:个)?(周|月)(?!前|后|内)', 'num_week_month'),  # 纯N周/N月

    (r'(凌晨|清晨|早上|上午|中午|下午|傍晚|晚上)?\s*(\d{1,2}):?(\d{0,2})?(点|时)?\s*[到至]\s*(\d{1,2}):?(\d{0,2})?(点|时)?', 'time_between'),  # [时段]HH:MM到HH:MM
    (r'(昨天|今天|明天)?\s*(凌晨|清晨|早上|上午|中午|下午|傍晚|晚上)\s*(\d+)(点|时)((\d+)分?|半)?', 'time_point'),  # 指定时段+时刻（支持“点/时”且分钟可省略“分”）
    (r'(\d{1,2}):?(\d{0,2})?(点|时|分)', 'time_point_hm'),  # 单点时刻
    (r'(下)?(星期|周)([一二三四五六日])到(下)?(星期|周)([一二三四五六日])', 'time_range_weekday'),  # 本/下周的星期区间
    (r'(昨天|今天|明天)?\s*(凌晨|清晨|早上|上午|中午|下午|傍晚|晚上)', 'time_period'),  # 指定时段（无具体时刻）
    (r'(上上|下下)(个)?(星期|周|礼拜)([一二三四五六日天])', 'double_relative_weekday'),  # 上上/下下周的某星期
    (r'(上上|下下)(个)?(星期|周|礼拜)?', 'double_relative_week'),  # 上上/下下周
    (r'((上|下|这|本)个)?礼拜([一二三四五六日天])', 'weekday'),  # 礼拜表达的星期
    (r'(\d{4})年(第)?([一二三四1234]|Q[1234]|q[1234])季度', 'specific_quarter_with_year'),  # 指定年份+季度
    (r'本季|本季度|上季度|下个季度|下季度', 'relative_quarter'),  # 相对季度
    (r'(第)?([一二三四1234]|Q[1234]|q[1234])季度', 'general_quarter'),  # 仅季度
    (r'(\d{4})年', 'specific_year'),  # 指定年份
    (r'前年|后年', 'before_after_year'),  # 前年/后年
    (r'本年|去年|今年|明年|来年', 'current_year_alias'),  # 相对年份别名
    (r'(上|下)一年', 'last_next_year'),  # 上一年/下一年
    (r'本(星期|周)?([一二三四五六日])', 'current_weekday'),  # 本周具体星期
    (r'下(星期|周)([一二三四五六日])', 'next_weekday'),  # 下周具体星期
    (r'本周|这个礼拜|本礼拜', 'current_week'),  # 本周
    (r'本月', 'current_month'),  # 本月
    (r'本日', 'current_day'),  # 本日
    (r'(上|下)周末', 'weekend'),  # 上/下周末
    (r'(上|下)个月', 'month'),  # 上/下个月
    (r'昨天|今天|明天', 'day'),  # 昨天/今天/明天
    (r'(\d+|零|一|二|两|三|四|五|六|七|八|九|十)(天|周|月|年)', 'num_time'),  # 纯数字+天/周/月/年
]


def get_day_range(dt) -> List[str]:
    """返回单日的0点-23:59:59区间"""
    return [
        dt.strftime('%Y-%m-%d 00:00:00'),
        dt.strftime('%Y-%m-%d 23:59:59')
    ]


def get_year_range(year) -> List[str]:
    """返回指定年份的起止时间"""
    year = max(MIN_YEAR, min(MAX_YEAR, year))
    first_day = datetime.datetime(year, 1, 1)
    last_day = datetime.datetime(year, 12, 31)
    return [
        first_day.strftime('%Y-%m-%d 00:00:00'),
        last_day.strftime('%Y-%m-%d 23:59:59')
    ]


def get_quarter_range(year, quarter_key) -> List[str]:
    """返回指定年份季度的起止时间"""
    year = max(MIN_YEAR, min(MAX_YEAR, year))
    quarter_key = str(quarter_key).lower()
    q_num, start_month, end_month = QUARTER_MAP[quarter_key]
    first_day = datetime.datetime(year, start_month, 1)
    if end_month == 12:
        last_day = datetime.datetime(year, 12, 31)
    else:
        last_day = datetime.datetime(year, end_month + 1, 1) - datetime.timedelta(days=1)
    return [
        first_day.strftime('%Y-%m-%d 00:00:00'),
        last_day.strftime('%Y-%m-%d 23:59:59')
    ]


def get_current_quarter(now: datetime.datetime) -> int:
    """根据月份返回当前季度序号"""
    m = now.month
    if m <= 3:
        return 1
    elif m <= 6:
        return 2
    elif m <= 9:
        return 3
    else:
        return 4


def get_current_month_range(now: datetime.datetime) -> List[str]:
    """返回当前月份的起止时间"""
    first = datetime.datetime(now.year, now.month, 1)
    if now.month == 12:
        last = datetime.datetime(now.year + 1, 1, 1) - datetime.timedelta(days=1)
    else:
        last = datetime.datetime(now.year, now.month + 1, 1) - datetime.timedelta(days=1)
    return [
        first.strftime('%Y-%m-%d 00:00:00'),
        last.strftime('%Y-%m-%d 23:59:59')
    ]


def get_weekday_from_base(base_dt, target_weekday_char) -> datetime.datetime:
    """从基准日期偏移到指定星期字符对应的日期"""
    target_wd = WEEKDAY_MAP[target_weekday_char]
    base_wd = base_dt.weekday()
    delta = target_wd - base_wd
    return base_dt + datetime.timedelta(days=delta)


def get_next_week_weekday(now, weekday_char) -> datetime.datetime:
    """返回下周指定星期几的日期"""
    wd = WEEKDAY_MAP[weekday_char]
    # 先找出下一周的周一，再偏移到目标星期几，避免直接+7造成跨周偏差
    next_monday = now - datetime.timedelta(days=now.weekday()) + datetime.timedelta(days=7)
    return next_monday + datetime.timedelta(days=wd)


def get_this_week_weekday(now, weekday_char) -> datetime.datetime:
    """返回本周指定星期几的日期（周日环回到下周）"""
    wd = WEEKDAY_MAP[weekday_char]
    days = (wd - now.weekday()) % 7
    return now + datetime.timedelta(days=days)


def get_current_week_range(now) -> List[str]:
    """返回本周周一到周日的时间区间"""
    monday = now - datetime.timedelta(days=now.weekday())
    sunday = monday + datetime.timedelta(days=6)
    return [
        monday.strftime('%Y-%m-%d 00:00:00'),
        sunday.strftime('%Y-%m-%d 23:59:59')
    ]


def parse_time_point(period, hour_str, minute_part) -> Tuple[int, int]:
    """解析“上午10点半”类时刻为24小时制的小时、分钟"""
    h = int(hour_str)
    h = max(0, min(23, h))
    # 将下午/傍晚/晚上视为下午时段，转换为24小时制
    if period in ['下午', '傍晚', '晚上'] and h < 12:
        h += 12
    elif period == '中午' and h == 0:
        h = 12
    elif period == '中午' and 1 <= h < 12:
        h = 12 if h == 12 else h + 12 if h <= 6 else h

    if minute_part == '半':
        m = 30
    elif minute_part:
        cleaned = minute_part.replace('分', '')
        if cleaned.isdigit():
            m = max(0, min(59, int(cleaned)))
        else:
            m = 0
    else:
        m = 0
    return h, m


def chinese_num_to_int(num_str) -> int:
    """将中文数字或数字字符串转为整数，超出范围做裁剪"""
    if num_str in CHINESE_NUM_MAP:
        num = CHINESE_NUM_MAP[num_str]
    elif num_str.isdigit():
        num = int(num_str)
    else:
        # 兜底默认值
        num = 1
        logger.warning(f"未匹配到数字，使用默认值：{num}")
    return max(1, min(1000, num))


def add_months(dt, n) -> datetime.datetime:
    """在日期上增加/减少 N 个月，自动调整年与日"""
    y = dt.year
    m = dt.month + n
    day = dt.day
    while m > 12:
        y += 1
        m -= 12
    while m < 1:
        y -= 1
        m += 12
    y = max(MIN_YEAR, min(MAX_YEAR, y))
    max_day = monthrange(y, m)[1]
    day = min(day, max_day)
    return datetime.datetime(y, m, day, dt.hour, dt.minute, dt.second)


def parse_hm_time(now, h, m) -> List[str]:
    """解析 10:30 类时刻为当天具体时间"""
    if m is None or m == '':
        m = 0
    try:
        m = int(m)
        h = int(h)
    except ValueError:
        h, m = 0, 0
    h = max(0, min(23, h))
    m = max(0, min(59, m))
    target = datetime.datetime(now.year, now.month, now.day, h, m)
    return [target.strftime('%Y-%m-%d %H:%M:%S')]


def parse_between_time(now, period, h1, m1, h2, m2, raw_text='') -> List[str]:
    """解析 10:00 到 12:00 类时间段，支持起始时段词并做 24 小时转换"""
    try:
        h1 = int(h1)
        h2 = int(h2)
        m1 = int(m1) if m1 and m1 != '' else 0
        m2 = int(m2) if m2 and m2 != '' else 0
    except ValueError:
        h1, m1, h2, m2 = 0, 0, 23, 59
    orig_h2 = h2
    h1 = max(0, min(23, h1))
    h2 = max(0, min(23, h2))
    m1 = max(0, min(59, m1))
    m2 = max(0, min(59, m2))

    # 若未捕获时段，尝试从原始片段推断
    if not period and raw_text:
        period = infer_period_from_text(raw_text)

    # 时段影响起始时间的 24 小时转换
    if period in ['下午', '傍晚', '晚上'] and h1 < 12:
        h1 += 12
        if h2 < 12:  # 若结束未标明时段且小于12，跟随起始时段做下午转换
            h2 += 12
    elif period == '中午' and h1 == 0:
        h1 = 12

    # 若起始时间晚于结束时间，尝试认为跨天到次日
    start = datetime.datetime(now.year, now.month, now.day, h1, m1)
    end = datetime.datetime(now.year, now.month, now.day, h2, m2)
    if start > end:
        # 若原始结束为 12 点且时段为晚上，视为次日 0 点
        if period in ['下午', '傍晚', '晚上'] and orig_h2 == 12:
            end = datetime.datetime(now.year, now.month, now.day, 0, m2) + datetime.timedelta(days=1)
        else:
            end += datetime.timedelta(days=1)

    return [start.strftime('%Y-%m-%d %H:%M:%S'), end.strftime('%Y-%m-%d %H:%M:%S')]


def calculate_hour_ago(now, num) -> List[str]:
    """计算 N 小时前的时间点"""
    num = max(1, min(1000, num))
    t = now - datetime.timedelta(hours=num)
    return [t.strftime('%Y-%m-%d %H:%M:%S')]


def calculate_hour_after(now, num) -> List[str]:
    """计算 N 小时后的时间点"""
    num = max(1, min(1000, num))
    t = now + datetime.timedelta(hours=num)
    return [t.strftime('%Y-%m-%d %H:%M:%S')]


def calculate_min_ago(now, num) -> List[str]:
    """计算 N 分钟前的时间点"""
    num = max(1, min(1440, num))
    t = now - datetime.timedelta(minutes=num)
    return [t.strftime('%Y-%m-%d %H:%M:%S')]


def calculate_min_after(now, num) -> List[str]:
    """计算 N 分钟后的时间点"""
    num = max(1, min(1440, num))
    t = now + datetime.timedelta(minutes=num)
    return [t.strftime('%Y-%m-%d %H:%M:%S')]


def calculate_time_ago(now, num, unit) -> List[str]:
    """根据单位计算 N 天/周/月/年前的时间范围"""
    logger.info(f"计算 {num} {unit} 前的时间，基准时间：{now}")
    num = max(1, min(100, num))
    if unit == '天':
        target_dt = now - datetime.timedelta(days=num)
        result = get_day_range(target_dt)
    elif unit == '周':
        this_monday = now - datetime.timedelta(days=now.weekday())
        target_monday = this_monday - datetime.timedelta(weeks=num)
        target_sunday = target_monday + datetime.timedelta(days=6)
        result = [
            target_monday.strftime('%Y-%m-%d 00:00:00'),
            target_sunday.strftime('%Y-%m-%d 23:59:59')
        ]
    elif unit == '月':
        target_dt = add_months(now, -num)
        first_day = datetime.datetime(target_dt.year, target_dt.month, 1)
        last_day = datetime.datetime(target_dt.year, target_dt.month, monthrange(target_dt.year, target_dt.month)[1])
        result = [
            first_day.strftime('%Y-%m-%d 00:00:00'),
            last_day.strftime('%Y-%m-%d 23:59:59')
        ]
    elif unit == '年':
        target_year = now.year - num
        result = get_year_range(target_year)
    else:
        result = []
    logger.info(f"计算结果：{result}")
    return result


def calculate_time_after(now, num, unit) -> List[str]:
    """根据单位计算 N 天/月/年后的时间范围"""
    num = max(1, min(100, num))
    if unit == '天':
        target_dt = now + datetime.timedelta(days=num)
        return get_day_range(target_dt)
    elif unit == '月':
        target_dt = add_months(now, num)
        first = datetime.datetime(target_dt.year, target_dt.month, 1)
        last = datetime.datetime(target_dt.year, target_dt.month, monthrange(target_dt.year, target_dt.month)[1])
        return [
            first.strftime('%Y-%m-%d 00:00:00'),
            last.strftime('%Y-%m-%d 23:59:59')
        ]
    elif unit == '年':
        target_year = now.year + num
        return get_year_range(target_year)
    return []


def calculate_near_time(now, num, unit) -> List[str]:
    """计算近 N 天/周/月/年的时间范围"""
    num = max(1, min(100, num))
    if unit == '天':
        start = now - datetime.timedelta(days=num - 1)
        return [
            start.strftime('%Y-%m-%d 00:00:00'),
            now.strftime('%Y-%m-%d 23:59:59')
        ]
    elif unit == '周':
        # 核心修复：近 N 周 = 从 N 周前的周一 到 本周日
        start_monday = now - datetime.timedelta(days=now.weekday() + (num - 1) * 7)
        end_sunday = start_monday + datetime.timedelta(days=7 * num - 1)
        return [
            start_monday.strftime('%Y-%m-%d 00:00:00'),
            end_sunday.strftime('%Y-%m-%d 23:59:59')
        ]
    elif unit == '月':
        start_dt = add_months(now, -(num - 1))
        first = datetime.datetime(start_dt.year, start_dt.month, 1)
        last = datetime.datetime(now.year, now.month, monthrange(now.year, now.month)[1])
        return [
            first.strftime('%Y-%m-%d 00:00:00'),
            last.strftime('%Y-%m-%d 23:59:59')
        ]
    elif unit == '年':
        start_year = now.year - num + 1
        first = datetime.datetime(start_year, 1, 1)
        last = datetime.datetime(now.year, 12, 31)
        return [
            first.strftime('%Y-%m-%d 00:00:00'),
            last.strftime('%Y-%m-%d 23:59:59')
        ]
    return []


def calculate_time_inner(now, num, unit) -> List[str]:
    """计算未来 N 天/周/月/年内的时间范围"""
    num = max(1, min(100, num))
    if unit == '天':
        end_dt = now + datetime.timedelta(days=num - 1)
        return [
            now.strftime('%Y-%m-%d 00:00:00'),
            end_dt.strftime('%Y-%m-%d 23:59:59')
        ]
    elif unit == '周':
        start_monday = now - datetime.timedelta(days=now.weekday())
        end_sunday = start_monday + datetime.timedelta(days=7 * num - 1)
        return [
            start_monday.strftime('%Y-%m-%d 00:00:00'),
            end_sunday.strftime('%Y-%m-%d 23:59:59')
        ]
    elif unit == '月':
        first = datetime.datetime(now.year, now.month, 1)
        end_dt = add_months(now, num - 1)
        last = datetime.datetime(end_dt.year, end_dt.month, monthrange(end_dt.year, end_dt.month)[1])
        return [
            first.strftime('%Y-%m-%d 00:00:00'),
            last.strftime('%Y-%m-%d 23:59:59')
        ]
    elif unit == '年':
        first = datetime.datetime(now.year, 1, 1)
        last = datetime.datetime(now.year + num - 1, 12, 31)
        return [
            first.strftime('%Y-%m-%d 00:00:00'),
            last.strftime('%Y-%m-%d 23:59:59')
        ]
    return []


def calculate_next_weekday(now, weekday_char) -> List[str]:
    """处理 “下个星期 X” 场景，返回单日区间"""
    dt = get_next_week_weekday(now, weekday_char)
    return get_day_range(dt)


def calculate_next_quarter(now) -> List[str]:
    """计算下个季度的起止时间"""
    y = now.year
    q = get_current_quarter(now)
    if q == 4:
        y += 1
        q = 1
    else:
        q += 1
    return get_quarter_range(y, str(q))


def calculate_num_week_month(now, num, unit) -> List[str]:
    """处理纯数字+周/月的时间范围，复用近N周/月逻辑"""
    num = chinese_num_to_int(num)
    if unit == '周':
        # 纯N周 = 近N周逻辑
        return calculate_near_time(now, num, '周')
    elif unit == '月':
        # 纯N月 = 近N月逻辑
        return calculate_near_time(now, num, '月')
    return []


def extract_chinese_time_range(text, now: datetime.datetime = None) -> List[str]:
    """解析中文时间表达并返回标准化时间范围/时间点列表"""
    if not text:
        logger.warning("输入文本为空")
        return []
    if now is None:
        now = datetime.datetime.now()

    # 遍历正则规则（按优先级）
    for idx, (pat, typ) in enumerate(PATTERNS):
        match_obj = re.search(pat, text)
        if not match_obj:
            continue

        logger.info(f"匹配到规则[{idx}]：类型={typ}，分组={match_obj.groups()}")

        if typ == 'next_weekday':
            weekday_char = match_obj.group(3)
            return calculate_next_weekday(now, weekday_char)

        if typ == 'next_quarter':
            return calculate_next_quarter(now)

        if typ == 'num_week_month':
            num_str = match_obj.group(1)
            unit = match_obj.group(2)
            return calculate_num_week_month(now, num_str, unit)

        if typ == 'num_time_ago':
            num_str = match_obj.group(1)
            unit = match_obj.group(2)
            num = chinese_num_to_int(num_str)
            return calculate_time_ago(now, num, unit)

        if typ == 'num_time_after':
            num_str = match_obj.group(1)
            unit = match_obj.group(2)
            num = chinese_num_to_int(num_str)
            return calculate_time_after(now, num, unit)

        if typ == 'num_time_inner':
            num_str = match_obj.group(1)
            unit = match_obj.group(2)
            num = chinese_num_to_int(num_str)
            return calculate_time_inner(now, num, unit)

        if typ == 'near_num_time':
            num_str = match_obj.group(1)
            unit = match_obj.group(2)
            num = chinese_num_to_int(num_str)
            return calculate_near_time(now, num, unit)

        if typ == 'num_hour_ago':
            num_str = match_obj.group(1)
            num = chinese_num_to_int(num_str)
            return calculate_hour_ago(now, num)

        if typ == 'num_hour_after':
            num_str = match_obj.group(1)
            num = chinese_num_to_int(num_str)
            return calculate_hour_after(now, num)

        if typ == 'num_min_ago':
            num_str = match_obj.group(1)
            num = chinese_num_to_int(num_str)
            return calculate_min_ago(now, num)

        if typ == 'num_min_after':
            num_str = match_obj.group(1)
            num = chinese_num_to_int(num_str)
            return calculate_min_after(now, num)

        if typ == 'time_between':
            period, h1, m1, _, h2, m2, _ = match_obj.groups()
            return parse_between_time(now, period, h1, m1, h2, m2, match_obj.group(0))

        if typ == 'time_point_hm':
            h, m, _ = match_obj.groups()
            return parse_hm_time(now, h, m)

        if typ == 'time_range_weekday':
            is_next = bool(match_obj.group(1))
            # 兼容所有分组写法：提取出现的星期字符
            weekday_chars = [g for g in match_obj.groups() if g in WEEKDAY_MAP]
            if len(weekday_chars) >= 2:
                start_wd, end_wd = weekday_chars[0], weekday_chars[-1]
            else:
                continue
            # 若文本含“下”，则以下周一为起点，否则默认本周
            if is_next:
                start_dt = get_next_week_weekday(now, start_wd)
            else:
                start_dt = get_this_week_weekday(now, start_wd)
            end_dt = get_weekday_from_base(start_dt, end_wd)
            return [get_day_range(start_dt)[0], get_day_range(end_dt)[1]]

        if typ == 'time_point':
            day = match_obj.group(1) or '今天'
            period = match_obj.group(2)
            h, m = parse_time_point(period, match_obj.group(3), match_obj.group(5))
            base = now
            if day == '昨天':
                base = now - datetime.timedelta(days=1)
            elif day == '明天':
                base = now + datetime.timedelta(days=1)
            return [datetime.datetime(base.year, base.month, base.day, h, m).strftime('%Y-%m-%d %H:%M:%S')]

        if typ == 'time_period':
            day = match_obj.group(1) or '今天'
            period = match_obj.group(2)
            base = now
            if day == '昨天':
                base = now - datetime.timedelta(days=1)
            elif day == '明天':
                base = now + datetime.timedelta(days=1)
            sh, eh, em = TIME_PERIOD_MAP[period]
            # 时段起止时间固定到当天，区间含起止分钟
            return [
                datetime.datetime(base.year, base.month, base.day, sh, 0).strftime('%Y-%m-%d %H:%M'),
                datetime.datetime(base.year, base.month, base.day, eh, em, 59).strftime('%Y-%m-%d %H:%M:%S')
            ]

        if typ == 'double_relative_weekday':
            direction = match_obj.group(1)
            weekday_char = match_obj.group(4)
            base_dt = get_this_week_weekday(now, weekday_char)
            current_wd = now.weekday()
            target_wd = WEEKDAY_MAP[weekday_char]
            diff_days = 14 if current_wd < target_wd else 21
            if direction == '上上':
                target_dt = base_dt - datetime.timedelta(days=diff_days)
            else:
                target_dt = base_dt + datetime.timedelta(days=diff_days)
            return get_day_range(target_dt)

        if typ == 'double_relative_week':
            direction = match_obj.group(1)
            this_monday = now - datetime.timedelta(days=now.weekday())
            if direction == '上上':
                target_monday = this_monday - datetime.timedelta(days=14)
            else:
                target_monday = this_monday + datetime.timedelta(days=14)
            target_sunday = target_monday + datetime.timedelta(days=6)
            return [
                target_monday.strftime('%Y-%m-%d 00:00:00'),
                target_sunday.strftime('%Y-%m-%d 23:59:59')
            ]

        if typ == 'weekday':
            prefix_part = match_obj.group(2)
            weekday_char = match_obj.group(3)
            base_dt = get_this_week_weekday(now, weekday_char)
            if prefix_part == '上':
                target_dt = base_dt - datetime.timedelta(days=7)
            elif prefix_part == '下':
                target_dt = base_dt + datetime.timedelta(days=7)
            else:
                target_dt = base_dt
            return get_day_range(target_dt)

        if typ == 'specific_quarter_with_year':
            year = int(match_obj.group(1))
            q_key = match_obj.group(3)
            return get_quarter_range(year, q_key)

        if typ == 'relative_quarter':
            word = match_obj.group(0)
            if word in ['本季', '本季度']:
                q = get_current_quarter(now)
                return get_quarter_range(now.year, str(q))
            elif word == '上季度':
                y = now.year
                q = get_current_quarter(now)
                if q == 1:
                    y -= 1
                    q = 4
                else:
                    q -= 1
                return get_quarter_range(y, str(q))
            elif word in ['下季度', '下个季度']:
                return calculate_next_quarter(now)

        if typ == 'general_quarter':
            q_key = match_obj.group(2)
            return get_quarter_range(now.year, q_key)

        if typ == 'specific_year':
            year = int(match_obj.group(1))
            return get_year_range(year)

        if typ == 'before_after_year':
            key = match_obj.group(0)
            y = now.year
            return get_year_range(y - 2 if key == '前年' else y + 2)

        if typ == 'current_year_alias':
            key = match_obj.group(0)
            y = now.year
            if key == '本年' or key == '今年':
                return get_year_range(y)
            elif key == '去年':
                return get_year_range(y - 1)
            else:
                return get_year_range(y + 1)

        if typ == 'last_next_year':
            y = now.year
            return get_year_range(y - 1 if match_obj.group(1) == '上' else y + 1)

        if typ == 'current_week':
            return get_current_week_range(now)

        if typ == 'current_month':
            return get_current_month_range(now)

        if typ == 'current_day':
            return get_day_range(now)

        if typ == 'current_weekday':
            dt = get_this_week_weekday(now, match_obj.group(2))
            return get_day_range(dt)

        if typ == 'next_weekday':
            dt = get_next_week_weekday(now, match_obj.group(2))
            return get_day_range(dt)

        if typ == 'weekend':
            this_sat = get_this_week_weekday(now, '六')
            sat = this_sat - datetime.timedelta(days=7) if match_obj.group(1) == '上' else this_sat + datetime.timedelta(days=7)
            sun = sat + datetime.timedelta(days=1)
            return [
                sat.strftime('%Y-%m-%d 00:00:00'),
                sun.strftime('%Y-%m-%d 23:59:59')
            ]

        if typ == 'month':
            cy, cm = now.year, now.month
            if match_obj.group(1) == '上':
                ty, tm = (cy - 1, 12) if cm == 1 else (cy, cm - 1)
            else:
                ty, tm = (cy + 1, 1) if cm == 12 else (cy, cm + 1)
            first = datetime.datetime(ty, tm, 1)
            last = datetime.datetime(ty, tm + 1, 1) - datetime.timedelta(days=1) if tm != 12 else datetime.datetime(ty + 1, 1, 1) - datetime.timedelta(
                days=1)
            return [
                first.strftime('%Y-%m-%d 00:00:00'),
                last.strftime('%Y-%m-%d 23:59:59')
            ]

        if typ == 'day':
            key = match_obj.group(0)
            dt = now
            if key == '昨天':
                dt = now - datetime.timedelta(days=1)
            elif key == '明天':
                dt = now + datetime.timedelta(days=1)
            return get_day_range(dt)

    return []


def infer_period_from_text(text: str) -> str:
    """从原始片段中推断时段关键词"""
    for key in ['凌晨', '清晨', '早上', '上午', '中午', '下午', '傍晚', '晚上']:
        if key in text:
            return key
    return ""
