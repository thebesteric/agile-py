from __future__ import annotations

import asyncio
import inspect
import json
import logging
import math
from collections.abc import Awaitable, Callable, Collection, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from functools import wraps
from http import HTTPStatus
from itertools import islice
from time import perf_counter
from typing import Annotated, Any, ParamSpec, TypeVar, cast, get_args, get_origin, get_type_hints, overload
from uuid import UUID

from pydantic import BaseModel

try:
    from starlette.requests import Request
    from starlette.responses import Response, StreamingResponse
except ModuleNotFoundError as import_error:
    if not import_error.name.startswith("starlette"):
        raise
    Request = Response = StreamingResponse = None

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")

_MAX_COLLECTION_ITEMS = 1_000
_MAX_STRING_LENGTH = 10_000
_MAX_PAYLOAD_LENGTH = 1_000_000


class CallRecord(BaseModel):
    """One function invocation, independent of database and authentication models."""

    api_name: str
    api_path: str
    http_method: str
    request_id: str | None = None
    client_ip: str | None = None
    request_payload: Any = None
    response_payload: Any = None
    status_code: int
    error_message: str | None = None
    start_at: datetime
    end_at: datetime
    duration_ms: float


RecordCallback = Callable[[CallRecord], Awaitable[None] | None]


def log_record(record: CallRecord) -> None:
    """Default storage callback: write one structured JSON record to logging."""
    logger.info(record.model_dump_json())


def _to_jsonable(value: Any, *, seen: set[int] | None = None, depth: int = 0) -> Any:
    if depth >= 10:
        return f"<{type(value).__name__}: max depth reached>"
    if isinstance(value, Enum):
        return _to_jsonable(value.value, seen=seen, depth=depth + 1)
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, str):
        if len(value) <= _MAX_STRING_LENGTH:
            return value
        return f"{value[:_MAX_STRING_LENGTH]}... [truncated {len(value) - _MAX_STRING_LENGTH} chars]"
    if isinstance(value, (bytes, bytearray)):
        return {"type": type(value).__name__, "size": len(value)}
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (UUID, Decimal)):
        return str(value)
    if Request is not None and isinstance(value, Request):
        return None
    if Response is not None and isinstance(value, Response):
        return {"type": type(value).__name__, "status_code": value.status_code}

    seen = seen if seen is not None else set()
    if id(value) in seen:
        return f"<{type(value).__name__}: circular reference>"
    seen.add(id(value))
    try:
        if isinstance(value, BaseModel):
            return _to_jsonable(value.model_dump(mode="python"), seen=seen, depth=depth + 1)
        if isinstance(value, Mapping):
            result = {
                str(key): _to_jsonable(item, seen=seen, depth=depth + 1)
                for key, item in islice(value.items(), _MAX_COLLECTION_ITEMS)
            }
            if len(value) > _MAX_COLLECTION_ITEMS:
                result["__truncated_items__"] = len(value) - _MAX_COLLECTION_ITEMS
            return result
        if isinstance(value, Sequence):
            result = [_to_jsonable(item, seen=seen, depth=depth + 1)
                      for item in islice(value, _MAX_COLLECTION_ITEMS)]
            if len(value) > _MAX_COLLECTION_ITEMS:
                result.append(f"... [{len(value) - _MAX_COLLECTION_ITEMS} items truncated]")
            return result
        if hasattr(value, "filename") and hasattr(value, "content_type"):
            return {
                "filename": str(value.filename or ""),
                "content_type": str(value.content_type or ""),
                "size": getattr(value, "size", None),
            }
        return f"<{type(value).__name__}>"
    finally:
        seen.remove(id(value))


def _limit_payload(payload: Any) -> Any:
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if len(encoded) <= _MAX_PAYLOAD_LENGTH:
        return payload
    return {"truncated": True, "original_length": len(encoded), "preview": encoded[:_MAX_PAYLOAD_LENGTH]}


def _request_payload(request: Any, signature: inspect.Signature,
                     args: tuple[Any, ...], kwargs: dict[str, Any], *,
                     redacted_headers: frozenset[str]) -> Any:
    payload: dict[str, Any] = {}
    if request is not None:
        payload["headers"] = {
            key: "[REDACTED]" if key.lower() in redacted_headers else request.headers.getlist(key)
            for key in request.headers
        }
        payload["path_params"] = dict(request.path_params)
        payload["query_params"] = {key: request.query_params.getlist(key) for key in request.query_params}
    arguments = signature.bind_partial(*args, **kwargs).arguments
    payload["arguments"] = {
        key: value for key, value in arguments.items()
        if not (Request is not None and isinstance(value, Request))
           and not (Response is not None and isinstance(value, Response))
    }
    return _limit_payload(_to_jsonable(payload))


def _response_payload(result: Any) -> Any:
    if StreamingResponse is not None and isinstance(result, StreamingResponse):
        return {"type": type(result).__name__, "media_type": result.media_type}
    if Response is not None and isinstance(result, Response):
        body = getattr(result, "body", None)
        if not body:
            return {"type": type(result).__name__}
        if len(body) > _MAX_PAYLOAD_LENGTH:
            return {"type": type(result).__name__, "body_size": len(body), "truncated": True}
        try:
            result = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {"type": type(result).__name__, "body_size": len(body)}
    return _limit_payload(_to_jsonable(result))


def _request_parameter(signature: inspect.Signature) -> tuple[str | None, inspect.Signature]:
    if Request is None:
        return None, signature
    for parameter in signature.parameters.values():
        annotation = parameter.annotation
        if get_origin(annotation) is Annotated:
            annotation = get_args(annotation)[0]
        if annotation is Request:
            return None, signature
    name = "recorder_request"
    while name in signature.parameters:
        name += "_"
    parameter = inspect.Parameter(name, inspect.Parameter.KEYWORD_ONLY, annotation=Request)
    parameters = list(signature.parameters.values())
    index = next((index for index, item in enumerate(parameters)
                  if item.kind is inspect.Parameter.VAR_KEYWORD), len(parameters))
    parameters.insert(index, parameter)
    return name, signature.replace(parameters=parameters)


def _status_code(result: Any, request: Any, response: Any) -> int:
    if Response is not None and isinstance(result, Response):
        return int(result.status_code)
    if response is not None and response.status_code is not None:
        return int(response.status_code)
    http_status = getattr(result, "http_status", None)
    if isinstance(http_status, int):
        return int(http_status)
    route = request.scope.get("route") if request is not None else None
    return int(getattr(route, "status_code", None) or HTTPStatus.OK)


async def _store_record(callback: RecordCallback, record: CallRecord) -> None:
    if inspect.iscoroutinefunction(callback):
        outcome = callback(record)
    else:
        outcome = await asyncio.to_thread(callback, record)
    if inspect.isawaitable(outcome):
        await outcome


def _store_record_sync(callback: RecordCallback, record: CallRecord) -> None:
    outcome = callback(record)
    if not inspect.isawaitable(outcome):
        return

    async def await_outcome() -> None:
        await outcome

    def run_callback() -> None:
        asyncio.run(await_outcome())

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        run_callback()
    else:
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="recorder") as executor:
            executor.submit(copy_context().run, run_callback).result()


def _decorate_recorder(func: Callable[P, T], *, name: str,
                       callback: RecordCallback, record_request: bool,
                       record_response: bool, redacted_headers: frozenset[str]) -> Callable[P, T]:
    if inspect.isgeneratorfunction(func) or inspect.isasyncgenfunction(func):
        raise TypeError("@recorder does not support generator functions")
    signature = inspect.signature(func)
    try:
        annotations = get_type_hints(inspect.unwrap(func), include_extras=True)
    except (NameError, TypeError):
        annotations = {}
    signature = signature.replace(
        parameters=[parameter.replace(annotation=annotations.get(parameter.name, parameter.annotation))
                    for parameter in signature.parameters.values()],
        return_annotation=annotations.get("return", signature.return_annotation),
    )
    injected_name, exposed_signature = _request_parameter(signature)

    def prepare_call(
            args: tuple[Any, ...], kwargs: dict[str, Any],
    ) -> tuple[dict[str, Any], Callable[[Any, BaseException | None], CallRecord]]:
        call_kwargs = dict(kwargs)
        injected_request = call_kwargs.pop(injected_name, None) if injected_name else None
        values = (injected_request, *args, *call_kwargs.values())
        request = next((value for value in values
                        if Request is not None and isinstance(value, Request)), None)
        response = next((value for value in values
                         if Response is not None and isinstance(value, Response)), None)
        start_at = datetime.now(UTC)
        started = perf_counter()

        def build_record(result: Any, error: BaseException | None) -> CallRecord:
            duration_ms = max(0.0, round((perf_counter() - started) * 1000, 3))
            end_at = datetime.now(UTC)
            status_code = HTTPStatus.INTERNAL_SERVER_ERROR.value
            if error is None:
                status_code = _status_code(result, request, response)
            else:
                error_status = getattr(error, "status_code", None)
                if isinstance(error_status, int):
                    status_code = int(error_status)
            error_message = str(error) if error is not None else None
            if error is None and (status_code >= 400 or getattr(result, "succeed", True) is False):
                error_message = getattr(result, "message", None)
            return CallRecord(
                api_name=name,
                api_path=request.url.path if request is not None else f"{func.__module__}.{func.__qualname__}",
                http_method=request.method if request is not None else "UNKNOWN",
                request_id=request.headers.get("x-request-id") if request is not None else None,
                client_ip=request.client.host if request is not None and request.client is not None else None,
                request_payload=_request_payload(
                    request, signature, args, call_kwargs, redacted_headers=redacted_headers,
                ) if record_request else None,
                response_payload=_response_payload(result) if record_response and error is None else None,
                status_code=status_code,
                error_message=str(error_message)[:_MAX_STRING_LENGTH] if error_message is not None else None,
                start_at=start_at,
                end_at=end_at,
                duration_ms=duration_ms,
            )

        return call_kwargs, build_record

    @wraps(func)
    async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
        call_kwargs, build_record = prepare_call(args, kwargs)
        result: Any = None
        error: BaseException | None = None
        try:
            result = await func(*args, **call_kwargs)
            return result
        except (Exception, asyncio.CancelledError) as exc:
            error = exc
            raise
        finally:
            try:
                await _store_record(callback, build_record(result, error))
            except Exception:
                logger.warning("Failed to record function call for %s", func.__qualname__, exc_info=True)

    @wraps(func)
    def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        call_kwargs, build_record = prepare_call(args, kwargs)
        result: Any = None
        error: BaseException | None = None
        try:
            result = func(*args, **call_kwargs)
            return result
        except (Exception, asyncio.CancelledError) as exc:
            error = exc
            raise
        finally:
            try:
                _store_record_sync(callback, build_record(result, error))
            except Exception:
                logger.warning("Failed to record function call for %s", func.__qualname__, exc_info=True)

    wrapper = async_wrapper if inspect.iscoroutinefunction(func) else sync_wrapper
    setattr(wrapper, "__signature__", exposed_signature)
    return cast(Callable[P, T], wrapper)


@overload
def recorder(func: Callable[P, T], /) -> Callable[P, T]: ...


@overload
def recorder(
        func: None = None, /, *, name: str | None = None, enable: bool = True,
        callback: RecordCallback | None = None, record_request: bool = True,
        record_response: bool = True, redacted_headers: Collection[str] | None = None,
) -> Callable[[Callable[P, T]], Callable[P, T]]: ...


def recorder(
        func: Callable[P, T] | None = None, /, *, name: str | None = None,
        enable: bool = True, callback: RecordCallback | None = None,
        record_request: bool = True, record_response: bool = True,
        redacted_headers: Collection[str] | None = None,
) -> Callable[P, T] | Callable[[Callable[P, T]], Callable[P, T]]:
    """Record sync/async function calls using a callback (JSON logging by default).

    Supports bare and configured decorator forms. Apply below the FastAPI route
    decorator. Wrappers preserve the function's sync/async nature and wait for
    storage before returning. Async functions offload synchronous callbacks to
    a worker thread. Sync functions run synchronous callbacks in the calling
    thread; awaitable callbacks run on a new event loop, using a worker thread
    if the calling thread already has a running loop. Such callbacks must not
    depend on resources bound to another loop. Storage failures are logged
    without changing the result or exception. Duration excludes storage and
    streaming-body iteration. FastAPI/Starlette integration is optional.
    Headers are not redacted by default. Set redacted_headers to a collection
    of names to mask only those recorded HTTP headers, ignoring name case.
    """
    for option, value in (("enable", enable), ("record_request", record_request),
                          ("record_response", record_response)):
        if not isinstance(value, bool):
            raise TypeError(f"recorder {option} must be a bool")
    if name is not None and not isinstance(name, str):
        raise TypeError("recorder name must be a string or None")
    if callback is not None and not callable(callback):
        raise TypeError("recorder callback must be callable or None")
    normalized_name = name.strip() if name else None
    if normalized_name and len(normalized_name) > 512:
        raise ValueError("recorder name must not exceed 512 characters")
    if redacted_headers is None:
        normalized_headers = frozenset()
    else:
        if isinstance(redacted_headers, (str, bytes, bytearray)) or not isinstance(redacted_headers, Collection):
            raise TypeError("recorder redacted_headers must be a collection of strings or None")
        if any(not isinstance(header_name, str) for header_name in redacted_headers):
            raise TypeError("recorder redacted_headers must contain only strings")
        if any(not header_name.strip() for header_name in redacted_headers):
            raise ValueError("recorder redacted_headers must not contain empty header names")
        normalized_headers = frozenset(header_name.strip().lower() for header_name in redacted_headers)

    def decorator(function: Callable[P, T]) -> Callable[P, T]:
        if not enable:
            return function
        return _decorate_recorder(
            function, name=normalized_name or f"{function.__module__}.{function.__qualname__}",
            callback=callback if callback is not None else log_record,
            record_request=record_request, record_response=record_response,
            redacted_headers=normalized_headers,
        )

    return decorator if func is None else decorator(func)
