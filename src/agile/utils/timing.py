import functools
import inspect
import time
from typing import Callable, Literal, Optional

from .log_helper import LogHelper

logger = LogHelper.get_logger()

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def timing(_func=None, *, func_name: Optional[str] = None, log_level: LogLevel = "INFO", precision: int = 3):
    """
    记录函数执行时间的装饰器，支持同步和异步函数
    :param _func: 被装饰的函数（如果直接调用装饰器）
    :param func_name: 自定义函数名称（用于日志），如果不提供则使用函数全限定名（module.qualname）
    :param log_level: 日志级别：DEBUG, INFO, WARNING, ERROR, CRITICAL
    :param precision: 时间精度（小数位数），默认 3 位（毫秒级）
    :return: 装饰器函数

    Usage example:
        @timing()
        def func():
            pass

        @timing(func_name="CustomName", log_level="DEBUG")
        def func():
            pass
    """

    def _format_time(_elapsed_time: float, _precision: int) -> str:
        """格式化时间"""
        if _elapsed_time < 1:
            return f"{_elapsed_time * 1000:.{_precision}f}ms"
        if _elapsed_time < 60:
            return f"{_elapsed_time:.{_precision}f}s"
        minutes = int(_elapsed_time // 60)
        seconds = _elapsed_time % 60
        return f"{minutes}m {seconds:.{_precision}f}s"

    def _log_success(display_name: str, start_time: float, *, is_async: bool = False) -> None:
        """记录成功执行的日志"""
        elapsed_time = time.perf_counter() - start_time
        time_str = _format_time(elapsed_time, precision)
        prefix = "Async function" if is_async else "Function"
        log_message = f"{prefix} '{display_name}' completed in {time_str}"
        log_method = getattr(logger, log_level.lower(), logger.info)
        log_method(log_message)

    def _log_error(display_name: str, start_time: float, err: Exception, *, is_async: bool = False) -> None:
        """记录执行失败的日志"""
        elapsed_time = time.perf_counter() - start_time
        time_str = _format_time(elapsed_time, precision)
        prefix = "Async function" if is_async else "Function"
        logger.error(f"{prefix} '{display_name}' failed after {time_str}, error: {err}", exc_info=True)

    def decorator(func: Callable) -> Callable:
        # 优先使用用户自定义名称，否则使用模块 + qualname 作为全限定名
        display_name = func_name or (
            f"{getattr(func, '__module__', '<unknown>')}."
            f"{getattr(func, '__qualname__', getattr(func, '__name__', '<callable>'))}"
        )
        is_coroutine = inspect.iscoroutinefunction(func)

        if is_coroutine:
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                start_time = time.perf_counter()
                try:
                    result = await func(*args, **kwargs)
                    _log_success(display_name, start_time, is_async=True)
                    return result
                except Exception as e:
                    _log_error(display_name, start_time, e, is_async=True)
                    raise

            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                _log_success(display_name, start_time, is_async=True)
                return result
            except Exception as e:
                _log_error(display_name, start_time, e, is_async=False)
                raise

        return sync_wrapper

    # 如果是 @timing 这种用法，_func 就是被装饰的函数，直接返回包装后的函数
    if _func is not None:
        return decorator(_func)

    # 如果是 @timing(...) 这种用法，返回真正的装饰器
    return decorator
