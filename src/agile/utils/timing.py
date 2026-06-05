import functools
import inspect
import time
from dataclasses import dataclass, field
import sys
import contextvars
import json
import re
from typing import Callable, Literal, Optional, List, Iterable

from .log_helper import LogHelper

logger = LogHelper.get_logger(title="[TIMING]")

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
TimingStackInclude = Literal["inclusive", "exclusive", "all"]
TimingStackOutput = Literal["text", "json"]

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


def timing_stack(
    _func=None,
    *,
    func_name: Optional[str] = None,
    log_level: LogLevel = "INFO",
    precision: int = 2,
    include: TimingStackInclude = "all",
    output_format: TimingStackOutput = "text",
    include_patterns: Optional[Iterable[str] | str] = None,
    exclude_patterns: Optional[Iterable[str] | str] = None,
):
    """
    记录函数完整调用栈的耗时，只需在最顶层函数上装饰一次。
    :param _func: 被装饰的函数（如果直接调用装饰器）
    :param func_name: 自定义函数名称（用于报告标题），如果不提供则使用函数名
    :param log_level: 日志级别：DEBUG, INFO, WARNING, ERROR, CRITICAL
    :param precision: 时间精度（毫秒小数位数），默认 2 位
    :param include: 输出耗时类型：inclusive/exclusive/all
    :param output_format: 输出格式：text/json
    :param include_patterns: 仅包含匹配的函数（支持 * 和 **）
    :param exclude_patterns: 排除匹配的函数（支持 * 和 **）
    :return: 装饰器函数
    """

    @dataclass
    class _CallNode:
        name: str
        start: float
        end: Optional[float] = None
        is_async: bool = False
        children: List["_CallNode"] = field(default_factory=list)

        @property
        def duration(self) -> float:
            if self.end is None:
                return 0.0
            return self.end - self.start

    _active_flag = contextvars.ContextVar("timing_stack_active", default=False)

    def _format_ms(_elapsed_time: float) -> str:
        return f"{_elapsed_time * 1000:.{precision}f} ms"

    def _normalize_patterns(patterns: Optional[Iterable[str] | str]) -> List[str]:
        if patterns is None:
            return []
        if isinstance(patterns, str):
            return [patterns]
        return list(patterns)

    def _compile_patterns(patterns: List[str]) -> List[re.Pattern]:
        compiled = []
        for pattern in patterns:
            escaped = re.escape(pattern)
            escaped = escaped.replace(r"\*\*", ".*")
            escaped = escaped.replace(r"\*", "[^.]*")
            compiled.append(re.compile(f"^{escaped}$"))
        return compiled

    include_list = _normalize_patterns(include_patterns)
    exclude_list = _normalize_patterns(exclude_patterns)
    include_regex = _compile_patterns(include_list) if include_list else []
    exclude_regex = _compile_patterns(exclude_list) if exclude_list else []

    def _match_any(name: str, patterns: List[re.Pattern]) -> bool:
        return any(pattern.fullmatch(name) for pattern in patterns)

    def _should_track(name: str) -> bool:
        if include_regex and not _match_any(name, include_regex):
            return False
        if exclude_regex and _match_any(name, exclude_regex):
            return False
        return True

    def decorator(func: Callable) -> Callable:
        report_title = func_name or getattr(func, "__name__", "<callable>")
        log_method = getattr(logger, log_level.lower(), logger.info)

        def _build_report(state, error: Optional[Exception]) -> None:
            # 生成完整调用树的统计报告
            roots = state["roots"]
            if roots:
                lines = [
                    "=" * 80,
                    f"📊 Function {report_title} full call stack timing",
                    "-" * 80
                ]

                def _exclusive_ms(node: _CallNode) -> float:
                    child_total = sum(child.duration for child in node.children)
                    return max(node.duration - child_total, 0.0)

                def _render(node: _CallNode, depth: int) -> None:
                    indent = "  " * depth
                    mode_label = "async" if node.is_async else "sync"
                    parts = [f"{indent}▶ {node.name}", mode_label]
                    if include in ("inclusive", "all"):
                        parts.append(f"inclusive = {_format_ms(node.duration)}")
                    if include in ("exclusive", "all"):
                        parts.append(f"exclusive = {_format_ms(_exclusive_ms(node))}")
                    lines.append(" | ".join(parts))
                    for child in node.children:
                        _render(child, depth + 1)

                if output_format == "json":
                    def _to_dict(node: _CallNode) -> dict:
                        return {
                            "name": node.name,
                            "mode": "async" if node.is_async else "sync",
                            "inclusive_ms": round(node.duration * 1000, precision),
                            "exclusive_ms": round(_exclusive_ms(node) * 1000, precision),
                            "children": [_to_dict(child) for child in node.children],
                        }

                    payload = {
                        "title": report_title,
                        "unit": "ms",
                        "include": include,
                        "roots": [_to_dict(root) for root in roots],
                    }
                    log_method(json.dumps(payload, ensure_ascii=True))
                else:
                    for root in roots:
                        _render(root, 1)
                    lines.append("=" * 80)
                    log_method("\n" + "\n".join(lines))

            if error is not None:
                logger.error(
                    f"Function '{report_title}' failed during timing stack profiling: {error}",
                    exc_info=True,
                )

        def _install_profile(state):
            # 使用 profiler 回调捕获函数 call/return 事件
            def _profile(frame, event, arg):
                if event not in ("call", "return", "exception"):
                    return _profile

                stack = state["stack"]
                tracked = state["tracked"]
                if event == "call":
                    module = frame.f_globals.get("__name__", "<unknown>")
                    name = frame.f_code.co_name
                    display_name = f"{module}.{name}"
                    if not _should_track(display_name):
                        return _profile

                    is_async = bool(frame.f_code.co_flags & inspect.CO_COROUTINE)
                    node = _CallNode(name=display_name, start=time.perf_counter(), is_async=is_async)
                    frame_id = id(frame)
                    tracked[frame_id] = node
                    if stack:
                        stack[-1].children.append(node)
                    else:
                        state["roots"].append(node)
                    stack.append(node)
                    return _profile

                frame_id = id(frame)
                node = tracked.get(frame_id)
                if node is None:
                    return _profile

                if stack and stack[-1] is node:
                    stack.pop()
                elif node in stack:
                    stack.remove(node)
                node.end = time.perf_counter()
                tracked.pop(frame_id, None)
                return _profile

            previous_profile = sys.getprofile()
            sys.setprofile(_profile)
            return previous_profile

        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                if _active_flag.get():
                    return await func(*args, **kwargs)

                state = {"stack": [], "roots": [], "tracked": {}}
                token = _active_flag.set(True)
                previous_profile = _install_profile(state)
                error: Optional[Exception] = None
                try:
                    result = await func(*args, **kwargs)
                except Exception as exc:
                    error = exc
                    raise
                finally:
                    sys.setprofile(previous_profile)
                    _active_flag.reset(token)
                    _build_report(state, error)

                return result

            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            if _active_flag.get():
                return func(*args, **kwargs)

            state = {"stack": [], "roots": [], "tracked": {}}

            token = _active_flag.set(True)
            previous_profile = _install_profile(state)
            error: Optional[Exception] = None
            try:
                result = func(*args, **kwargs)
            except Exception as exc:
                error = exc
                raise
            finally:
                sys.setprofile(previous_profile)
                _active_flag.reset(token)
                _build_report(state, error)

            return result

        return sync_wrapper

    if _func is not None:
        return decorator(_func)

    return decorator