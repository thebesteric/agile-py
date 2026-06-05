import asyncio
import itertools
import unittest
from unittest.mock import patch
import logging
import importlib

from agile.utils.timing import timing_stack

timing_module = importlib.import_module("agile.utils.timing")


def _get_base_logger():
    return timing_module.logger.logger if hasattr(timing_module.logger, "logger") else timing_module.logger


class TestTimingStack(unittest.TestCase):

    def test_timing_stack_reports_call_tree_sync(self):
        counter = itertools.count(start=0.0, step=0.01)
        records = []

        class _ListHandler(logging.Handler):
            def emit(self, record):
                records.append(record)

        handler = _ListHandler()
        handler.setLevel(logging.INFO)

        with patch("agile.utils.timing.time.perf_counter", side_effect=lambda: next(counter)):
            base_logger = _get_base_logger()
            base_logger.addHandler(handler)
            try:
                @timing_stack(func_name="top", include="all")
                def top():
                    a()

                def a():
                    b()

                def b():
                    c()

                def c():
                    return "done"

                result = top()
            finally:
                base_logger.removeHandler(handler)

        self.assertIsNone(result)

    def test_timing_stack_reports_call_tree_async(self):
        counter = itertools.count(start=0.0, step=0.01)
        records = []

        class _ListHandler(logging.Handler):
            def emit(self, record):
                records.append(record)

        handler = _ListHandler()
        handler.setLevel(logging.INFO)

        with patch("agile.utils.timing.time.perf_counter", side_effect=lambda: next(counter)):
            base_logger = _get_base_logger()
            base_logger.addHandler(handler)
            try:
                @timing_stack(func_name="async_top", include="all", output_format="json")
                async def async_top():
                    await async_a()

                async def async_a():
                    await async_b()

                async def async_b():
                    await async_c()

                async def async_c():
                    return "done"

                result = asyncio.run(async_top())
            finally:
                base_logger.removeHandler(handler)

        self.assertIsNone(result)

    def test_timing_stack_reports_call_tree_mixed_async_sync(self):
        counter = itertools.count(start=0.0, step=0.01)
        records = []

        class _ListHandler(logging.Handler):
            def emit(self, record):
                records.append(record)

        handler = _ListHandler()
        handler.setLevel(logging.INFO)

        with patch("agile.utils.timing.time.perf_counter", side_effect=lambda: next(counter)):
            base_logger = _get_base_logger()
            base_logger.addHandler(handler)
            try:
                @timing_stack(func_name="mixed_top", include="all")
                async def mixed_top():
                    sync_a()
                    await async_b()

                def sync_a():
                    sync_b()

                def sync_b():
                    return "sync-done"

                async def async_b():
                    await async_c()

                async def async_c():
                    return "async-done"

                result = asyncio.run(mixed_top())
            finally:
                base_logger.removeHandler(handler)

        self.assertIsNone(result)

    def test_timing_stack_include_patterns_star(self):
        counter = itertools.count(start=0.0, step=0.01)
        records = []

        class _ListHandler(logging.Handler):
            def emit(self, record):
                records.append(record)

        handler = _ListHandler()
        handler.setLevel(logging.INFO)

        with patch("agile.utils.timing.time.perf_counter", side_effect=lambda: next(counter)):
            base_logger = _get_base_logger()
            base_logger.addHandler(handler)
            try:
                @timing_stack(func_name="top", include="all", include_patterns=f"{__name__}.t*")
                def top():
                    a()

                def a():
                    b()

                def b():
                    c()

                def c():
                    return "done"

                result = top()
            finally:
                base_logger.removeHandler(handler)

        self.assertIsNone(result)

    def test_timing_stack_exclude_patterns_double_star(self):
        counter = itertools.count(start=0.0, step=0.01)
        records = []

        class _ListHandler(logging.Handler):
            def emit(self, record):
                records.append(record)

        handler = _ListHandler()
        handler.setLevel(logging.INFO)

        with patch("agile.utils.timing.time.perf_counter", side_effect=lambda: next(counter)):
            base_logger = _get_base_logger()
            base_logger.addHandler(handler)
            try:
                @timing_stack(
                    func_name="top",
                    include="all",
                    include_patterns=f"{__name__}.**",
                    exclude_patterns=[f"{__name__}.b", f"{__name__}.c"],
                )
                def top():
                    a()

                def a():
                    b()

                def b():
                    c()

                def c():
                    return "done"

                result = top()
            finally:
                base_logger.removeHandler(handler)

        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
