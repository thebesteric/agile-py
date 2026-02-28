import datetime
import json
import os
from pathlib import Path
from typing import Any, Union, Type

import dotenv

# 支持的变量类型（类型对象而非值）
VarType = Union[
    Type[str], Type[bool], Type[int], Type[float], Type[list], Type[dict], Type[tuple], Type[set], Type[datetime.datetime], Type[datetime.date], Type[
        datetime.time], Type[None]]


class EnvHelper:
    ACCEPT_BOOL_TRUE_VALUES = {"true", "1", "yes", "on", "enable"}
    ACCEPT_BOOL_FALSE_VALUES = {"false", "0", "no", "off", "disable"}
    ACCEPT_NONE_VALUES = {"none", "null", "nil"}
    ACCEPT_DATETIME_FORMATS = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d"]
    ACCEPT_DATE_FORMATS = ["%Y-%m-%d", "%Y/%m/%d"]
    ACCEPT_TIME_FORMATS = ["%H:%M:%S", "%H:%M"]

    def __init__(self, env_file_path: str | Path = None, override: bool = False):
        """
        初始化环境变量读取器
        :param env_file_path: 环境变量文件路径
        :param override: 是否覆盖系统环境变量
        """
        dotenv.load_dotenv(dotenv_path=env_file_path, override=override)

    def set(self, key: str, value: Any) -> None:
        """
        设置环境变量值，自动进行类型序列化
        :param key: 环境变量的键
        :param value: 要设置的值（可以是任何类型）
        :raises ValueError: 当 key 为空时抛出
        :raises TypeError: 当值类型不支持序列化时抛出
        """
        if not key:
            raise ValueError("Environment variable key cannot be empty")

        # 序列化值为字符串
        str_value = self._serialize_value(value)

        # 设置环境变量
        os.environ[key] = str_value

    def get_required(self, key: str, var_type: VarType = None) -> Any:
        """
        获取必需的环境变量值，如果不存在则抛出异常

        不同于 get() 方法，此方法不支持默认值，当环境变量不存在时会抛出 KeyError

        :param key: 环境变量的键
        :param var_type: 期望的类型，如果提供则尝试将值转换为该类型
        :return: 转换后的值
        :raises KeyError: 当环境变量不存在时抛出
        :raises ValueError: 当 key 为空或类型转换失败时抛出
        :raises TypeError: 当不支持的类型传入时抛出
        """
        if not key:
            raise ValueError("Environment variable key cannot be empty")

        raw_value = os.getenv(key)

        # 环境变量不存在，抛出异常
        if raw_value is None:
            raise KeyError(f"Required environment variable '{key}' is not set")

        return self.get(key, default=None, var_type=var_type)

    def get(self, key: str, default: Any = None, var_type: VarType = None) -> Any:
        """
        获取环境变量值，并进行类型转换
        :param key: 环境变量的键
        :param default: 默认值，如果环境变量不存在则返回该值
        :param var_type: 期望的类型，如果提供则尝试将值转换为该类型
        :return: 转换后的值或默认值
        :raises ValueError: 当类型转换失败时抛出
        :raises TypeError: 当不支持的类型传入时抛出
        """
        if not key:
            raise ValueError("Environment variable key cannot be empty")

        raw_value = os.getenv(key)

        # 环境变量不存在，返回默认值
        if raw_value is None:
            return default

        # 处理空字符串（特殊场景：值为 "" 时转换为 None）
        raw_value = raw_value.strip()
        if raw_value == "" and var_type is type(None):
            return None

        try:
            if var_type is not None:
                return self._convert_to_type(raw_value, var_type)
            else:
                return self._auto_convert(raw_value)
        except (ValueError, TypeError, json.JSONDecodeError) as e:
            raise TypeError(f"Environment variable {key} with value '{raw_value}' cannot be converted to the specified type: {e}") from e

    @classmethod
    def _serialize_value(cls, value: Any) -> str:
        """
        将值序列化为字符串以供设置环境变量
        :param value: 要序列化的值
        :return: 序列化后的字符串
        :raises TypeError: 当值类型不支持序列化时抛出
        """
        # None
        if value is None:
            return "none"

        # 布尔值
        elif isinstance(value, bool):
            return "true" if value else "false"

        # 整数和浮点数
        elif isinstance(value, (int, float)):
            return str(value)

        # 字符串
        elif isinstance(value, str):
            return value

        # datetime.datetime
        elif isinstance(value, datetime.datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")

        # datetime.date（必须在 datetime 之后检查）
        elif isinstance(value, datetime.date):
            return value.strftime("%Y-%m-%d")

        # datetime.time
        elif isinstance(value, datetime.time):
            return value.strftime("%H:%M:%S")

        # list/dict/tuple/set → JSON
        elif isinstance(value, (list, dict, tuple, set)):
            try:
                # set 需要转换为 list 以支持 JSON 序列化
                if isinstance(value, set):
                    return json.dumps(list(value))
                else:
                    return json.dumps(value)
            except (TypeError, ValueError) as e:
                raise TypeError(f"Cannot serialize value of type {type(value).__name__}: {e}") from e

        # 不支持的类型
        else:
            raise TypeError(f"Unsupported value type for serialization: {type(value).__name__}")

    @classmethod
    def _convert_to_type(cls, raw_value: str, target_type: VarType):
        """
        将字符串值转换为指定类型
        :param raw_value: 原始字符串值
        :param target_type: 目标变量类型
        :return: 转换后的值
        :raises ValueError: 当值无法转换为目标类型时抛出
        :raises TypeError: 当不支持的类型传入时抛出
        """
        value = raw_value.strip()
        lower_value = value.lower()
        # 布尔值
        if target_type is bool:
            if lower_value in cls.ACCEPT_BOOL_TRUE_VALUES:
                return True
            elif lower_value in cls.ACCEPT_BOOL_FALSE_VALUES:
                return False
            else:
                raise ValueError(f"Cannot convert to bool: {raw_value}")
        # None 类型
        elif target_type is type(None):
            if lower_value in cls.ACCEPT_NONE_VALUES:
                return None
            else:
                raise ValueError(f"Cannot convert to None type: {raw_value}")
        # 整数
        elif target_type is int:
            return int(value)
        # 浮点数
        elif target_type is float:
            return float(value)
        # 字符串
        elif target_type is str:
            return value
        # 列表（支持 JSON 格式字符串，如 "[1,2,3]"）
        elif target_type is list:
            parsed = json.loads(value)
            if not isinstance(parsed, list):
                raise ValueError(f"The value '{raw_value}' is not a valid list format")
            return parsed
        # 字典（支持 JSON 格式字符串，如 '{"key":"value"}'）
        elif target_type is dict:
            parsed = json.loads(value)
            if not isinstance(parsed, dict):
                raise ValueError(f"The value '{raw_value}' is not a valid dict format")
            return parsed
        # 元组（先转列表再转元组，支持 JSON 格式字符串，如 "[1,2,3]"）
        elif target_type is tuple:
            parsed = json.loads(value)
            if not isinstance(parsed, list):
                raise ValueError(f"The value '{raw_value}' cannot be converted to a tuple (must be a valid list format)")
            return tuple(parsed)
        # Set 集合（先转列表再转 Set 集合，支持 JSON 格式字符串，如 "[1,2,3]"）
        elif target_type is set:
            parsed = json.loads(value)
            if not isinstance(parsed, list):
                raise ValueError(f"The value '{raw_value}' cannot be converted to a set (must be a valid list format)")
            return set(parsed)
        # 日期时间（支持 ISO 格式，如 "2026-02-28 12:30:00" 或 "2026-02-28"）
        elif target_type is datetime.datetime:
            # 支持的时间格式列表，按优先级匹配
            for fmt in cls.ACCEPT_DATETIME_FORMATS:
                try:
                    return datetime.datetime.strptime(value, fmt)
                except ValueError:
                    continue
            raise ValueError(f"Cannot convert to datetime type (supported formats: {cls.ACCEPT_DATETIME_FORMATS}): {raw_value}")
        # 日期（支持格式，如 "2026-02-28" 或 "2026/02/28"）
        elif target_type is datetime.date:
            # 支持的日期格式列表，按优先级匹配
            for fmt in cls.ACCEPT_DATE_FORMATS:
                try:
                    return datetime.datetime.strptime(value, fmt).date()
                except ValueError:
                    continue
            raise ValueError(f"Cannot convert to date type (supported formats: {cls.ACCEPT_DATE_FORMATS}): {raw_value}")
        # 时间（支持格式，如 "12:30:00" 或 "12:30"）
        elif target_type is datetime.time:
            # 支持的时间格式列表，按优先级匹配
            for fmt in cls.ACCEPT_TIME_FORMATS:
                try:
                    return datetime.datetime.strptime(value, fmt).time()
                except ValueError:
                    continue
            raise ValueError(f"Cannot convert to time type (supported formats: {cls.ACCEPT_TIME_FORMATS}): {raw_value}")
        # 不支持的类型
        else:
            raise TypeError(f"Unsupported target type: {target_type}")

    @classmethod
    def _auto_convert(cls, raw_value: str) -> Any:
        """
        自动推断字符串类型并转换
        :param raw_value: 原始字符串值
        :return: 转换后的值（类型由转换逻辑自动推断）
        """
        lower_value = raw_value.lower()

        # 处理 None
        if lower_value in cls.ACCEPT_NONE_VALUES:
            return None
        # 处理布尔值
        if lower_value in cls.ACCEPT_BOOL_TRUE_VALUES | cls.ACCEPT_BOOL_FALSE_VALUES:
            return cls._convert_to_type(raw_value, bool)
        # 处理整数
        try:
            return int(raw_value)
        except ValueError:
            pass
        # 处理浮点数
        try:
            return float(raw_value)
        except ValueError:
            pass
        # 处理列表/字典/元组（通过 JSON 格式识别）
        try:
            parsed = json.loads(raw_value)
            if isinstance(parsed, (list, dict, tuple)):
                return parsed
        except json.JSONDecodeError:
            pass
        # 处理日期时间，尝试按优先级匹配: date > datetime > time
        # 尝试 date 格式（更严格，必须是纯日期）
        for fmt in cls.ACCEPT_DATE_FORMATS:
            try:
                return datetime.datetime.strptime(raw_value, fmt).date()
            except ValueError:
                continue
        # 尝试 datetime 格式（更宽松，包含时间部分）
        for fmt in cls.ACCEPT_DATETIME_FORMATS:
            try:
                return datetime.datetime.strptime(raw_value, fmt)
            except ValueError:
                continue
        # 尝试 time 格式
        for fmt in cls.ACCEPT_TIME_FORMATS:
            try:
                return datetime.datetime.strptime(raw_value, fmt).time()
            except ValueError:
                continue
        # 返回原始字符串
        return raw_value.strip()
