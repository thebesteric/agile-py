import asyncio
import time
import unittest
from unittest.mock import patch

from agile.utils import timing


class Foo:

    @timing
    def work(self):
        return "done"


@timing
async def async_work():
    return "async-done"


@timing
async def async_fail_work():
    raise RuntimeError("async-boom")


@timing(func_name="custom.display")
def custom_name_work():
    return "custom-done"


@timing
def fail_work():
    raise ValueError("boom")


class TestTiming(unittest.TestCase):

    def test_sync_uses_fully_qualified_name(self):
        with patch("agile.utils.timing.time.perf_counter", side_effect=[1.0, 1.2]), \
                patch("agile.utils.timing.logger") as mock_logger:
            result = Foo().work()

            self.assertEqual("done", result)
            mock_logger.info.assert_called_once()
            log_message = mock_logger.info.call_args.args[0]
            expected_name = f"{Foo.work.__module__}.{Foo.work.__qualname__}"
            print(f"==> 函数 '{expected_name}' 执行完成", log_message)

    def test_async_uses_fully_qualified_name(self):
        with patch("agile.utils.timing.time.perf_counter", side_effect=[2.0, 2.3]), \
                patch("agile.utils.timing.logger") as mock_logger:
            result = asyncio.run(async_work())

            self.assertEqual("async-done", result)
            mock_logger.info.assert_called_once()
            log_message = mock_logger.info.call_args.args[0]
            expected_name = f"{async_work.__module__}.{async_work.__qualname__}"
            print(f"==> 函数 '{expected_name}' 执行完成", log_message)

    def test_func_name_override_takes_precedence(self):
        with patch("agile.utils.timing.time.perf_counter", side_effect=[3.0, 3.1]), \
                patch("agile.utils.timing.logger") as mock_logger:
            result = custom_name_work()

            self.assertEqual("custom-done", result)
            mock_logger.info.assert_called_once()
            log_message = mock_logger.info.call_args.args[0]
            print(f"==> 函数 'custom.display' 执行完成", log_message)

    def test_sync_exception_logs_error_and_reraises(self):
        with patch("agile.utils.timing.time.perf_counter", side_effect=[4.0, 4.15]), \
                patch("agile.utils.timing.logger") as mock_logger:
            with self.assertRaisesRegex(ValueError, "boom"):
                fail_work()

            mock_logger.error.assert_called_once()
            error_message = mock_logger.error.call_args.args[0]
            error_kwargs = mock_logger.error.call_args.kwargs
            expected_name = f"{fail_work.__module__}.{fail_work.__qualname__}"
            print(f"==> 函数 '{expected_name}' 执行失败", error_message)

    def test_async_exception_logs_error_and_reraises(self):
        with patch("agile.utils.timing.time.perf_counter", side_effect=[5.0, 5.2]), \
                patch("agile.utils.timing.logger") as mock_logger:
            with self.assertRaisesRegex(RuntimeError, "async-boom"):
                asyncio.run(async_fail_work())

            mock_logger.error.assert_called_once()
            error_message = mock_logger.error.call_args.args[0]
            error_kwargs = mock_logger.error.call_args.kwargs
            expected_name = f"{async_fail_work.__module__}.{async_fail_work.__qualname__}"
            print(f"==> 异步函数 '{expected_name}' 执行失败", error_message)
            self.assertTrue(error_kwargs.get("exc_info"))

    def test_real_sleep_duration_close_to_expected(self):
        target_seconds = 1.5

        @timing(func_name="real.sleep.test")
        def real_sleep_work():
            time.sleep(target_seconds)
            return "real-done"

        start = time.perf_counter()
        result = real_sleep_work()
        elapsed = time.perf_counter() - start

        self.assertEqual("real-done", result)
        self.assertGreaterEqual(elapsed, 1.5)

    def test_inline_func(self):

        def inline_func(foo: str):
            time.sleep(2)
            print(f"==> {foo} 内联函数执行完成")
            return "inline_func"

        decorated = timing(inline_func)
        print(decorated("test"))


if __name__ == '__main__':
    unittest.main()
