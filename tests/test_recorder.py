from __future__ import annotations

import asyncio
import inspect
import json
import subprocess
import sys
import threading
import unittest
from contextvars import ContextVar
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from http import HTTPStatus
from importlib import import_module
from typing import Annotated
from unittest.mock import patch
from uuid import UUID

from pydantic import BaseModel

from agile.utils import CallRecord, RecordCallback, log_record, recorder
from agile.web import R
from agile.utils.recorder import _limit_payload, _to_jsonable

try:
    from fastapi import FastAPI, HTTPException, Request, Response
    from fastapi.responses import JSONResponse, StreamingResponse
    from fastapi.testclient import TestClient
except ImportError:
    FastAPI = None

MODULE = "agile.utils.recorder"


class ItemRequest(BaseModel):
    name: str


class TestRecorder(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.records: list[CallRecord] = []

    async def save(self, record: CallRecord) -> None:
        await asyncio.sleep(0)
        self.records.append(record)

    async def test_success_preserves_result_and_records_arguments(self):
        result = {"id": 12}

        @recorder(name="  get item  ", callback=self.save)
        async def endpoint(item_id: int):
            return result

        with patch(f"{MODULE}.perf_counter", side_effect=[10.0, 10.125]):
            self.assertIs(await endpoint(12), result)
        record = self.records[0]
        self.assertEqual(record.api_name, "get item")
        self.assertEqual(record.request_payload["arguments"], {"item_id": 12})
        self.assertEqual(record.response_payload, result)
        self.assertEqual(record.status_code, 200)
        self.assertEqual(record.duration_ms, 125.0)
        self.assertEqual(record.start_at.tzinfo, UTC)
        self.assertLessEqual(record.start_at, record.end_at)
        self.assertIsNone(record.error_message)
        self.assertEqual(record.http_method, "UNKNOWN")

    async def test_all_decorator_forms_default_to_json_logging(self):
        async def endpoint():
            return {"ok": True}

        for decorate in (recorder(), recorder(name="custom")):
            with self.subTest(decorate=decorate), patch(f"{MODULE}.logger") as logger:
                decorated = decorate(endpoint)
                self.assertEqual(await decorated(), {"ok": True})
                logger.info.assert_called_once()
                record = json.loads(logger.info.call_args.args[0])
                self.assertEqual(record["status_code"], 200)
                self.assertEqual(record["response_payload"], {"ok": True})
                self.assertEqual(decorated.__name__, endpoint.__name__)
                self.assertIs(decorated.__wrapped__, endpoint)
        self.assertEqual(recorder.__name__, "recorder")

    async def test_sync_callback_runs_in_worker_with_context(self):
        context = ContextVar("request_id", default=None)
        context.set("request-123")
        caller_thread = threading.get_ident()
        observed = []

        def save(record):
            observed.append((threading.get_ident(), context.get(), record))

        @recorder(callback=save)
        async def endpoint():
            return "ok"

        self.assertEqual(await endpoint(), "ok")
        self.assertNotEqual(observed[0][0], caller_thread)
        self.assertEqual(observed[0][1], "request-123")
        self.assertIsInstance(observed[0][2], CallRecord)

    async def test_callable_object_and_returned_awaitable_are_supported(self):
        class AsyncStorage:
            async def __call__(storage, record):
                await self.save(record)

        for callback in (AsyncStorage(), lambda record: self.save(record)):
            with self.subTest(callback=callback):
                @recorder(callback=callback)
                async def endpoint():
                    return "ok"

                self.assertEqual(await endpoint(), "ok")
        self.assertEqual(len(self.records), 2)

    async def test_original_exception_is_recorded_and_reraised(self):
        failure = ValueError("invalid item")

        @recorder(callback=self.save)
        async def endpoint():
            raise failure

        with self.assertRaises(ValueError) as caught:
            await endpoint()
        self.assertIs(caught.exception, failure)
        self.assertEqual(self.records[0].status_code, 500)
        self.assertEqual(self.records[0].error_message, "invalid item")
        self.assertIsNone(self.records[0].response_payload)

    async def test_storage_failure_does_not_change_result_or_original_exception(self):
        def sync_failure(record):
            raise RuntimeError("storage unavailable")

        async def async_failure(record):
            raise RuntimeError("storage unavailable")

        failure = ValueError("endpoint failure")
        for callback in (sync_failure, async_failure):
            for should_fail in (False, True):
                with self.subTest(callback=callback, should_fail=should_fail):
                    @recorder(callback=callback)
                    async def endpoint():
                        if should_fail:
                            raise failure
                        return "ok"

                    with patch(f"{MODULE}.logger") as logger:
                        if should_fail:
                            with self.assertRaises(ValueError) as caught:
                                await endpoint()
                            self.assertIs(caught.exception, failure)
                        else:
                            self.assertEqual(await endpoint(), "ok")
                        logger.warning.assert_called_once()

    async def test_instrumentation_failure_does_not_change_result(self):
        @recorder(callback=self.save)
        async def endpoint():
            return "ok"

        with patch(f"{MODULE}._status_code", side_effect=RuntimeError("invalid status")), \
                patch(f"{MODULE}.logger") as logger:
            self.assertEqual(await endpoint(), "ok")
            logger.warning.assert_called_once()

    async def test_recording_flags_skip_payload_builders(self):
        @recorder(callback=self.save, record_request=False, record_response=False)
        async def endpoint():
            return {"secret": "value"}

        with patch(f"{MODULE}._request_payload") as request_builder, \
                patch(f"{MODULE}._response_payload") as response_builder:
            await endpoint()
        request_builder.assert_not_called()
        response_builder.assert_not_called()
        self.assertIsNone(self.records[0].request_payload)
        self.assertIsNone(self.records[0].response_payload)

    async def test_cancelled_endpoint_is_recorded_and_cancellation_propagates(self):
        @recorder(callback=self.save)
        async def endpoint():
            raise asyncio.CancelledError("cancelled")

        with self.assertRaises(asyncio.CancelledError):
            await endpoint()
        self.assertEqual(self.records[0].status_code, 500)
        self.assertEqual(self.records[0].error_message, "cancelled")

    async def test_cancellation_during_callback_is_not_swallowed(self):
        started = asyncio.Event()

        async def save(record):
            started.set()
            await asyncio.Event().wait()

        @recorder(callback=save)
        async def endpoint():
            return "ok"

        task = asyncio.create_task(endpoint())
        await started.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

    async def test_business_response_status_and_error_message(self):
        result = R.error(http_status=HTTPStatus.CONFLICT, message="conflict")

        @recorder(callback=self.save)
        async def endpoint():
            return result

        self.assertIs(await endpoint(), result)
        self.assertEqual(self.records[0].status_code, 409)
        self.assertEqual(self.records[0].error_message, "conflict")

    async def test_disabled_decorator_returns_original_function(self):
        async def endpoint():
            return "ok"

        self.assertIs(recorder(enable=False)(endpoint), endpoint)

    async def test_sync_function_with_async_callback_inside_running_loop(self):
        context = ContextVar("sync_request_id", default=None)
        context.set("request-123")
        calling_loop = asyncio.get_running_loop()
        calling_thread = threading.get_ident()
        observed = []

        async def save(record):
            await asyncio.sleep(0)
            observed.append((asyncio.get_running_loop(), threading.get_ident(), context.get()))
            self.records.append(record)

        @recorder(callback=save)
        def calculate(value: int):
            return value * 2

        self.assertEqual(calculate(6), 12)
        self.assertFalse(inspect.iscoroutinefunction(calculate))
        self.assertIsNot(observed[0][0], calling_loop)
        self.assertNotEqual(observed[0][1], calling_thread)
        self.assertEqual(observed[0][2], "request-123")
        self.assertEqual(self.records[0].response_payload, 12)

    async def test_plain_endpoint_can_keep_unresolved_forward_annotations(self):
        @recorder(callback=self.save)
        async def endpoint() -> "UnresolvedResponse":
            return "ok"

        self.assertEqual(await endpoint(), "ok")
        self.assertEqual(self.records[0].status_code, 200)

    async def test_sync_function_returning_awaitable_keeps_original_result(self):
        async def value():
            return 12

        result = value()

        @recorder(callback=self.records.append)
        def calculate():
            return result

        returned = calculate()
        self.assertIs(returned, result)
        self.assertEqual(await returned, 12)
        self.assertEqual(self.records[0].response_payload, "<coroutine>")

    async def test_sync_function_callback_failure_inside_running_loop_is_isolated(self):
        async def failing_save(record):
            await asyncio.sleep(0)
            raise RuntimeError("storage unavailable")

        failure = ValueError("calculation failed")
        for should_fail in (False, True):
            with self.subTest(should_fail=should_fail):
                @recorder(callback=failing_save)
                def calculate():
                    if should_fail:
                        raise failure
                    return 12

                with patch(f"{MODULE}.logger") as logger:
                    if should_fail:
                        with self.assertRaises(ValueError) as caught:
                            calculate()
                        self.assertIs(caught.exception, failure)
                    else:
                        self.assertEqual(calculate(), 12)
                    logger.warning.assert_called_once()

    @unittest.skipIf(FastAPI is None, "FastAPI is not installed")
    async def test_streaming_response_is_not_consumed(self):
        consumed = []

        async def chunks():
            consumed.append(True)
            yield b"data"

        result = StreamingResponse(chunks(), media_type="text/plain", status_code=202)

        @recorder(callback=self.save)
        async def endpoint():
            return result

        self.assertIs(await endpoint(), result)
        self.assertEqual(consumed, [])
        self.assertEqual(self.records[0].status_code, 202)
        self.assertEqual(self.records[0].response_payload,
                         {"type": "StreamingResponse", "media_type": "text/plain"})
        await result.body_iterator.aclose()


class TestRecorderSync(unittest.TestCase):
    def setUp(self):
        self.records: list[CallRecord] = []

    def test_success_preserves_sync_result_metadata_and_duration(self):
        result = {"total": 12}

        def calculate(value: int):
            """Calculate a total."""
            return result

        wrapped = recorder(callback=self.records.append)(calculate)
        with patch(f"{MODULE}.perf_counter", side_effect=[10.0, 10.125]):
            self.assertIs(wrapped(6), result)
        self.assertFalse(inspect.iscoroutinefunction(wrapped))
        self.assertIs(wrapped.__wrapped__, calculate)
        self.assertEqual(wrapped.__name__, calculate.__name__)
        self.assertEqual(wrapped.__doc__, calculate.__doc__)
        record = self.records[0]
        self.assertEqual(record.api_name, f"{calculate.__module__}.{calculate.__qualname__}")
        self.assertEqual(record.api_path, record.api_name)
        self.assertEqual(record.http_method, "UNKNOWN")
        self.assertEqual(record.request_payload["arguments"], {"value": 6})
        self.assertEqual(record.response_payload, result)
        self.assertEqual(record.status_code, 200)
        self.assertEqual(record.duration_ms, 125.0)
        self.assertEqual(record.start_at.tzinfo, UTC)
        self.assertLessEqual(record.start_at, record.end_at)
        self.assertIsNone(record.error_message)

    def test_all_decorator_forms_default_to_json_logging(self):
        def calculate():
            return 12

        for decorate in (recorder, recorder(), recorder(name="custom")):
            with self.subTest(decorate=decorate), patch(f"{MODULE}.logger") as logger:
                self.assertEqual(decorate(calculate)(), 12)
                logger.info.assert_called_once()
                record = json.loads(logger.info.call_args.args[0])
                self.assertEqual(record["status_code"], 200)
                self.assertEqual(record["response_payload"], 12)

    def test_sync_callback_runs_in_calling_thread_with_context(self):
        context = ContextVar("request_id", default=None)
        context.set("request-123")
        calling_thread = threading.get_ident()
        observed = []

        def save(record):
            observed.append((threading.get_ident(), context.get(), record))

        @recorder(callback=save)
        def calculate():
            self.assertEqual(threading.get_ident(), calling_thread)
            return 12

        self.assertEqual(calculate(), 12)
        self.assertEqual(observed[0][:2], (calling_thread, "request-123"))
        self.assertIsInstance(observed[0][2], CallRecord)

    def test_async_callbacks_and_returned_awaitables_are_waited_for(self):
        context = ContextVar("request_id", default=None)
        context.set("request-123")

        async def save(record):
            await asyncio.sleep(0)
            self.assertEqual(context.get(), "request-123")
            self.records.append(record)

        class AsyncStorage:
            async def __call__(storage, record):
                await save(record)

        for callback in (save, AsyncStorage(), lambda record: save(record)):
            with self.subTest(callback=callback):
                previous_count = len(self.records)

                @recorder(callback=callback)
                def calculate():
                    return 12

                self.assertEqual(calculate(), 12)
                self.assertEqual(len(self.records), previous_count + 1)

    def test_original_exception_is_recorded_and_reraised(self):
        failure = ValueError("invalid value")

        @recorder(callback=self.records.append)
        def calculate():
            raise failure

        with self.assertRaises(ValueError) as caught:
            calculate()
        self.assertIs(caught.exception, failure)
        self.assertEqual(self.records[0].status_code, 500)
        self.assertEqual(self.records[0].error_message, "invalid value")
        self.assertIsNone(self.records[0].response_payload)

    def test_storage_failure_preserves_result_or_original_exception(self):
        def sync_failure(record):
            raise RuntimeError("storage unavailable")

        async def async_failure(record):
            await asyncio.sleep(0)
            raise RuntimeError("storage unavailable")

        failure = ValueError("calculation failed")
        for callback in (sync_failure, async_failure):
            for should_fail in (False, True):
                with self.subTest(callback=callback, should_fail=should_fail):
                    @recorder(callback=callback)
                    def calculate():
                        if should_fail:
                            raise failure
                        return 12

                    with patch(f"{MODULE}.logger") as logger:
                        if should_fail:
                            with self.assertRaises(ValueError) as caught:
                                calculate()
                            self.assertIs(caught.exception, failure)
                        else:
                            self.assertEqual(calculate(), 12)
                        logger.warning.assert_called_once()

    def test_recording_flags_skip_payload_builders(self):
        @recorder(callback=self.records.append, record_request=False, record_response=False)
        def calculate():
            return 12

        with patch(f"{MODULE}._request_payload") as request_builder, \
                patch(f"{MODULE}._response_payload") as response_builder:
            self.assertEqual(calculate(), 12)
        request_builder.assert_not_called()
        response_builder.assert_not_called()
        self.assertIsNone(self.records[0].request_payload)
        self.assertIsNone(self.records[0].response_payload)

    def test_instrumentation_failure_does_not_change_result(self):
        @recorder(callback=self.records.append)
        def calculate():
            return 12

        with patch(f"{MODULE}._status_code", side_effect=RuntimeError("invalid status")), \
                patch(f"{MODULE}.logger") as logger:
            self.assertEqual(calculate(), 12)
            logger.warning.assert_called_once()

    def test_instance_class_and_static_methods_preserve_binding(self):
        save = self.records.append

        class Calculator:
            factor = 2

            @recorder(callback=save)
            def multiply(self, value: int):
                return self.factor * value

            @classmethod
            @recorder(callback=save)
            def class_multiply(cls, value: int):
                return cls.factor * value

            @staticmethod
            @recorder(callback=save)
            def static_multiply(value: int):
                return value * 2

        self.assertEqual(Calculator().multiply(6), 12)
        self.assertEqual(Calculator.class_multiply(6), 12)
        self.assertEqual(Calculator.static_multiply(6), 12)
        self.assertEqual([record.response_payload for record in self.records], [12, 12, 12])

    def test_business_response_status_and_error_message(self):
        @recorder(callback=self.records.append)
        def calculate():
            return R.error(http_status=HTTPStatus.CONFLICT, message="conflict")

        calculate()
        self.assertEqual(self.records[0].status_code, 409)
        self.assertEqual(self.records[0].error_message, "conflict")

    def test_disabled_decorator_returns_original_function(self):
        def calculate():
            return 12

        self.assertIs(recorder(enable=False)(calculate), calculate)
        self.assertEqual(calculate(), 12)


class TestRecorderConfiguration(unittest.TestCase):
    def test_public_exports_point_to_recorder_module(self):
        module = import_module(MODULE)
        self.assertIs(recorder, module.recorder)
        self.assertIs(CallRecord, module.CallRecord)
        self.assertIs(RecordCallback, module.RecordCallback)
        self.assertIs(log_record, module.log_record)
        self.assertEqual(recorder.__module__, MODULE)
        self.assertEqual(CallRecord.__module__, MODULE)
        self.assertEqual(log_record.__module__, MODULE)
        self.assertFalse(hasattr(module, "__all__"))

    def test_invalid_configuration(self):
        for options in ({"enable": 1}, {"record_request": "yes"}, {"record_response": None},
                        {"name": 123}, {"callback": "database"}):
            with self.subTest(options=options), self.assertRaises(TypeError):
                recorder(**options)
        with self.assertRaises(ValueError):
            recorder(name="a" * 513)

    def test_invalid_redacted_headers_configuration(self):
        invalid_collections = (
            "Authorization", b"Authorization", bytearray(b"Authorization"), 123,
            iter(["Authorization"]), {"Authorization", 123}, ["Authorization", None],
        )
        for headers in invalid_collections:
            with self.subTest(headers=headers), self.assertRaises(TypeError):
                recorder(redacted_headers=headers)
        for headers in ([""], {"   "}, ("\t",)):
            with self.subTest(headers=headers), self.assertRaises(ValueError):
                recorder(redacted_headers=headers)

    def test_generator_functions_are_rejected(self):
        def generator():
            yield 12

        async def async_generator():
            yield 12

        for function in (generator, async_generator):
            with self.subTest(function=function), self.assertRaisesRegex(TypeError, "generator"):
                recorder(function)

    def test_serialization_is_bounded_and_json_compatible(self):
        class State(Enum):
            READY = "ready"

        circular = []
        circular.append(circular)
        identifier = UUID("12345678-1234-5678-1234-567812345678")
        result = _to_jsonable({
            "date": datetime(2026, 1, 1, tzinfo=UTC), "decimal": Decimal("1.25"),
            "uuid": identifier, "enum": State.READY, "binary": b"secret",
            "model": ItemRequest(name="example"), "nan": float("nan"),
            "circular": circular, "large": list(range(1_100)), "text": "a" * 11_000,
        })
        json.dumps(result, allow_nan=False)
        self.assertEqual(result["uuid"], str(identifier))
        self.assertEqual(result["decimal"], "1.25")
        self.assertEqual(result["enum"], "ready")
        self.assertEqual(result["binary"], {"type": "bytes", "size": 6})
        self.assertEqual(result["model"], {"name": "example"})
        self.assertIn("circular reference", result["circular"][0])
        self.assertEqual(len(result["large"]), 1_001)
        self.assertIn("truncated", result["text"])
        self.assertTrue(_limit_payload({"text": "a" * 1_000_001})["truncated"])

    def test_works_without_starlette(self):
        script = '''
import asyncio
import builtins
original_import = builtins.__import__
def without_starlette(name, *args, **kwargs):
    if name == "starlette" or name.startswith("starlette."):
        raise ModuleNotFoundError("starlette is not installed", name="starlette")
    return original_import(name, *args, **kwargs)
builtins.__import__ = without_starlette
from agile.utils import recorder
records = []
@recorder(callback=records.append, redacted_headers={"Authorization"})
async def endpoint(value: int):
    return value
assert asyncio.run(endpoint(12)) == 12
assert records[0].status_code == 200
assert records[0].request_payload["arguments"] == {"value": 12}
@recorder(callback=records.append)
def calculate(value: int):
    return value * 2
assert calculate(6) == 12
assert records[1].status_code == 200
assert records[1].request_payload["arguments"] == {"value": 6}
'''
        result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)


@unittest.skipIf(FastAPI is None, "FastAPI is not installed")
class TestRecorderFastAPI(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.records = []
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)

    def test_injected_request_and_forward_referenced_model(self):
        @self.app.post("/items/{item_id}", status_code=201)
        @recorder(callback=self.records.append)
        async def endpoint(item_id: int, payload: ItemRequest):
            return {"id": item_id, "name": payload.name}

        response = self.client.post(
            "/items/12?tag=a&tag=b", json={"name": "example"},
            headers={
                "x-request-id": "request-123", "authorization": "Bearer secret", "cookie": "secret=1",
                "proxy-authorization": "Basic proxy", "x-api-key": "private-key",
            },
        )
        self.assertEqual(response.status_code, 201)
        record = self.records[0]
        self.assertEqual(record.api_path, "/items/12")
        self.assertEqual(record.http_method, "POST")
        self.assertEqual(record.status_code, 201)
        self.assertEqual(record.request_id, "request-123")
        self.assertIsNotNone(record.client_ip)
        self.assertEqual(record.request_payload["query_params"], {"tag": ["a", "b"]})
        self.assertEqual(record.request_payload["path_params"], {"item_id": "12"})
        self.assertEqual(record.request_payload["headers"]["authorization"], ["Bearer secret"])
        self.assertEqual(record.request_payload["headers"]["cookie"], ["secret=1"])
        self.assertEqual(record.request_payload["headers"]["proxy-authorization"], ["Basic proxy"])
        self.assertEqual(record.request_payload["headers"]["x-api-key"], ["private-key"])
        self.assertEqual(record.request_payload["arguments"], {"item_id": 12, "payload": {"name": "example"}})
        parameters = self.app.openapi()["paths"]["/items/{item_id}"]["post"]["parameters"]
        self.assertNotIn("recorder_request", [parameter["name"] for parameter in parameters])

    def test_header_redaction_is_case_insensitive_and_does_not_change_request(self):
        observed_headers = []

        def sync_endpoint(request: Request):
            observed_headers.append(request.headers.getlist("authorization"))
            return {"ok": True}

        async def async_endpoint(request: Request):
            return sync_endpoint(request)

        headers = [
            ("Authorization", "Bearer first"), ("Authorization", "Bearer second"),
            ("X-Custom-Secret", "private"), ("Cookie", "session=secret"), ("X-Trace", "visible"),
        ]
        for collection_type in (set, frozenset, list, tuple):
            for function in (sync_endpoint, async_endpoint):
                with self.subTest(collection_type=collection_type, function=function):
                    path = f"/redacted/{collection_type.__name__}/{function.__name__}"
                    wrapped = recorder(
                        callback=self.records.append,
                        redacted_headers=collection_type(["  aUtHoRiZaTiOn  ", "X-Custom-Secret"]),
                    )(function)
                    self.app.add_api_route(path, wrapped, methods=["GET"])
                    response = self.client.get(path, headers=headers)
                    self.assertEqual(response.status_code, 200)
                    recorded_headers = self.records[-1].request_payload["headers"]
                    self.assertEqual(recorded_headers["authorization"], "[REDACTED]")
                    self.assertEqual(recorded_headers["x-custom-secret"], "[REDACTED]")
                    self.assertEqual(recorded_headers["cookie"], ["session=secret"])
                    self.assertEqual(recorded_headers["x-trace"], ["visible"])
                    self.assertEqual(observed_headers[-1], ["Bearer first", "Bearer second"])

    def test_none_and_empty_collections_do_not_redact_headers(self):
        def endpoint(request: Request):
            return {"ok": True}

        for index, headers in enumerate((None, set(), frozenset(), [], ())):
            with self.subTest(headers=headers):
                path = f"/unredacted/{index}"
                wrapped = recorder(callback=self.records.append, redacted_headers=headers)(endpoint)
                self.app.add_api_route(path, wrapped, methods=["GET"])
                response = self.client.get(path, headers={"Authorization": "Bearer secret", "Cookie": "secret=1"})
                self.assertEqual(response.status_code, 200)
                recorded_headers = self.records[-1].request_payload["headers"]
                self.assertEqual(recorded_headers["authorization"], ["Bearer secret"])
                self.assertEqual(recorded_headers["cookie"], ["secret=1"])

    def test_header_configuration_is_copied_and_isolated_per_function(self):
        headers_to_redact = {"Authorization"}

        @self.app.get("/redact-authorization")
        @recorder(callback=self.records.append, redacted_headers=headers_to_redact)
        async def first():
            return {"ok": True}

        headers_to_redact.clear()
        headers_to_redact.add("Cookie")

        @self.app.get("/redact-cookie")
        @recorder(callback=self.records.append, redacted_headers=headers_to_redact)
        async def second():
            return {"ok": True}

        headers_to_redact.clear()
        headers = {"Authorization": "Bearer secret", "Cookie": "secret=1"}
        self.assertEqual(self.client.get("/redact-authorization", headers=headers).status_code, 200)
        self.assertEqual(self.client.get("/redact-cookie", headers=headers).status_code, 200)
        first_headers = self.records[0].request_payload["headers"]
        second_headers = self.records[1].request_payload["headers"]
        self.assertEqual(first_headers["authorization"], "[REDACTED]")
        self.assertEqual(first_headers["cookie"], ["secret=1"])
        self.assertEqual(second_headers["authorization"], ["Bearer secret"])
        self.assertEqual(second_headers["cookie"], "[REDACTED]")

    def test_explicit_annotated_request_is_not_duplicated(self):
        @self.app.get("/explicit")
        @recorder(callback=self.records.append)
        async def endpoint(request: Annotated[Request, "request context"]):
            return {"path": request.url.path}

        self.assertNotIn("recorder_request", inspect.signature(endpoint).parameters)
        self.assertEqual(self.client.get("/explicit").json(), {"path": "/explicit"})
        self.assertEqual(self.records[0].request_payload["arguments"], {})

    def test_quoted_forward_references_are_resolved_in_endpoint_namespace(self):
        @self.app.post("/quoted")
        @recorder(callback=self.records.append)
        async def endpoint(request: "Request", payload: "ItemRequest") -> "ItemRequest":
            return payload

        self.assertNotIn("recorder_request", inspect.signature(endpoint).parameters)
        response = self.client.post("/quoted", json={"name": "example"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"name": "example"})
        self.assertEqual(self.records[0].api_path, "/quoted")

    def test_response_status_precedence(self):
        @self.app.get("/injected", status_code=201)
        @recorder(callback=self.records.append)
        async def injected(response: Response):
            response.status_code = 202
            return {"ok": True}

        @self.app.get("/returned", status_code=201)
        @recorder(callback=self.records.append)
        async def returned(response: Response):
            response.status_code = 202
            return JSONResponse({"error": "conflict"}, status_code=409)

        self.assertEqual(self.client.get("/injected").status_code, 202)
        self.assertEqual(self.records[-1].status_code, 202)
        self.assertEqual(self.client.get("/returned").status_code, 409)
        self.assertEqual(self.records[-1].status_code, 409)
        self.assertEqual(self.records[-1].response_payload, {"error": "conflict"})

    def test_http_exception_is_unchanged(self):
        @self.app.get("/missing")
        @recorder(callback=self.records.append)
        async def endpoint():
            raise HTTPException(status_code=404, detail="not found", headers={"x-error": "missing"})

        response = self.client.get("/missing")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "not found"})
        self.assertEqual(response.headers["x-error"], "missing")
        self.assertEqual(self.records[0].status_code, 404)
        self.assertIn("not found", self.records[0].error_message)
        self.assertIsNone(self.records[0].response_payload)

    def test_injected_parameter_avoids_names_and_precedes_kwargs(self):
        @recorder(callback=self.records.append)
        async def endpoint(recorder_request: str, **kwargs):
            return recorder_request

        parameters = list(inspect.signature(endpoint).parameters.values())
        self.assertEqual(parameters[-2].name, "recorder_request_")
        self.assertIs(parameters[-2].annotation, Request)
        self.assertEqual(parameters[-1].kind, inspect.Parameter.VAR_KEYWORD)

    def test_sync_route_keeps_threadpool_execution_and_request_injection(self):
        function_threads = []
        callback_threads = []

        def save(record):
            callback_threads.append(threading.get_ident())
            self.records.append(record)

        @self.app.post("/sync/{item_id}", status_code=201)
        @recorder(callback=save)
        def endpoint(item_id: int, payload: ItemRequest, response: Response):
            function_threads.append(threading.get_ident())
            response.status_code = 202
            return {"id": item_id, "name": payload.name}

        self.assertFalse(inspect.iscoroutinefunction(endpoint))
        response = self.client.post("/sync/12", json={"name": "example"},
                                    headers={"x-request-id": "sync-123"})
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json(), {"id": 12, "name": "example"})
        self.assertEqual(callback_threads, function_threads)
        record = self.records[0]
        self.assertEqual(record.api_path, "/sync/12")
        self.assertEqual(record.http_method, "POST")
        self.assertEqual(record.status_code, 202)
        self.assertEqual(record.request_id, "sync-123")
        self.assertEqual(record.request_payload["arguments"], {"item_id": 12, "payload": {"name": "example"}})

    def test_sync_route_with_async_callback_preserves_http_exception(self):
        async def save(record):
            await asyncio.sleep(0)
            self.records.append(record)

        @self.app.get("/sync-missing")
        @recorder(callback=save)
        def endpoint(request: Request):
            raise HTTPException(status_code=404, detail="not found")

        response = self.client.get("/sync-missing")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "not found"})
        self.assertEqual(self.records[0].status_code, 404)
        self.assertEqual(self.records[0].api_path, "/sync-missing")
        self.assertIn("not found", self.records[0].error_message)


if __name__ == "__main__":
    unittest.main()
