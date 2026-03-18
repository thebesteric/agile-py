import threading
import unittest

from numpy.ma.core import outer

from agile.utils import singleton

@singleton
class Service:
    def __init__(self):
        print("Service.__init__")

outer_service = Service()

class TestSingleton(unittest.TestCase):

    def test_returns_same_instance(self):
        """验证同一个单例类重复实例化时返回同一对象。"""


        first = Service()
        second = Service()

        self.assertIs(first, second)
        self.assertIs(first, outer_service)

    def test_init_only_runs_once(self):
        """验证多次构造仅首次执行 __init__，后续参数不覆盖已有状态。"""
        @singleton
        class CounterService:
            init_count = 0

            def __init__(self, value: int):
                type(self).init_count += 1
                self.value = value

        first = CounterService(1)
        second = CounterService(2)

        self.assertIs(first, second)
        self.assertEqual(1, CounterService.init_count)
        self.assertEqual(1, first.value)
        self.assertEqual(1, second.value)

    def test_monitor_info_contains_expected_fields(self):
        """验证 monitor_info 返回类名、创建信息与调用次数。"""
        @singleton
        class MonitorService:
            pass

        MonitorService()
        MonitorService()
        info = MonitorService.monitor_info()

        self.assertEqual("MonitorService", info["class_name"])
        self.assertIn("created_at", info)
        self.assertIn("thread_name", info)
        self.assertEqual(2, info["call_count"])

    def test_destroy_recreates_instance_and_uses_explicit_close(self):
        """验证 destroy 优先调用 close 释放资源，并在下一次构造时重建实例。"""
        @singleton
        class ResourceService:
            close_count = 0
            del_count = 0

            def close(self):
                type(self).close_count += 1

            def __del__(self):
                type(self).del_count += 1

        first = ResourceService()
        ResourceService.destroy()
        second = ResourceService()

        self.assertEqual(1, ResourceService.close_count)
        # destroy 应优先走显式释放接口，不手动调用 __del__
        self.assertEqual(0, ResourceService.del_count)
        self.assertIsNot(first, second)

    def test_destroy_without_explicit_release_still_recreates_instance(self):
        """验证未提供显式释放方法时，destroy 仍能清理并允许实例重建。"""
        @singleton
        class LegacyResourceService:
            pass

        first = LegacyResourceService()
        LegacyResourceService.destroy()
        second = LegacyResourceService()

        self.assertIsNot(first, second)

    def test_destroy_prefers_close_over_dispose(self):
        """验证同时存在 close/dispose 时优先选择 close。"""
        @singleton
        class DualResourceService:
            close_count = 0
            dispose_count = 0

            def close(self):
                type(self).close_count += 1

            def dispose(self):
                type(self).dispose_count += 1

        DualResourceService()
        DualResourceService.destroy()

        self.assertEqual(1, DualResourceService.close_count)
        self.assertEqual(0, DualResourceService.dispose_count)

    def test_init_runs_once_across_multiple_call_sites(self):
        """验证不同调用入口创建同一单例时，__init__ 仍只执行一次。"""
        @singleton
        class MultiSiteService:
            init_count = 0

            def __init__(self):
                type(self).init_count += 1

        def build_from_a():
            return MultiSiteService()

        def build_from_b():
            return MultiSiteService()

        first = build_from_a()
        second = build_from_b()

        self.assertIs(first, second)
        self.assertEqual(1, MultiSiteService.init_count)

        MultiSiteService.destroy()
        third = build_from_a()

        self.assertIsNot(first, third)
        self.assertEqual(2, MultiSiteService.init_count)

    def test_concurrent_creation_returns_single_instance(self):
        """验证并发创建场景下仍保持单例，并统计正确调用次数。"""
        @singleton
        class ConcurrentService:
            init_count = 0

            def __init__(self):
                type(self).init_count += 1

        worker_count = 16
        start_barrier = threading.Barrier(worker_count)
        results = [None] * worker_count

        def worker(index: int):
            start_barrier.wait()
            results[index] = ConcurrentService()

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(worker_count)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        instance_ids = {id(item) for item in results}
        self.assertEqual(1, len(instance_ids))
        self.assertEqual(1, ConcurrentService.init_count)

        info = ConcurrentService.monitor_info()
        self.assertEqual(worker_count, info["call_count"])

    def test_concurrent_create_destroy_interleaving_stress(self):
        """验证并发 create/destroy 交替压力下不抛异常且最终可恢复单例语义。"""
        @singleton
        class StressService:
            init_count = 0

            def __init__(self):
                type(self).init_count += 1

        creator_threads = 8
        destroyer_threads = 4
        rounds = 200
        start_barrier = threading.Barrier(creator_threads + destroyer_threads)
        errors = []
        errors_lock = threading.Lock()

        def creator_worker():
            try:
                start_barrier.wait()
                for _ in range(rounds):
                    instance = StressService()
                    self.assertIsNotNone(instance)
            except Exception as exc:
                with errors_lock:
                    errors.append(exc)

        def destroyer_worker():
            try:
                start_barrier.wait()
                for _ in range(rounds):
                    StressService.destroy()
            except Exception as exc:
                with errors_lock:
                    errors.append(exc)

        creators = [threading.Thread(target=creator_worker) for _ in range(creator_threads)]
        destroyers = [threading.Thread(target=destroyer_worker) for _ in range(destroyer_threads)]
        threads = creators + destroyers

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual([], errors)

        # 压测后仍可恢复到可用状态，并保持单例语义
        first = StressService()
        second = StressService()
        self.assertIs(first, second)
        self.assertGreaterEqual(StressService.init_count, 1)

        info = StressService.monitor_info()
        self.assertEqual("StressService", info["class_name"])
        self.assertGreaterEqual(info["call_count"], 1)


if __name__ == "__main__":
    unittest.main()
