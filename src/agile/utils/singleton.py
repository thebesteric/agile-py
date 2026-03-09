import threading
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, ConfigDict

from .log_helper import LogHelper

logger = LogHelper.get_logger()


class MonitorData(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    created_at: str = Field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        description="创建时间"
    )
    thread_name: str = Field(
        default_factory=lambda: threading.current_thread().name,
        description="创建线程名称"
    )
    call_count: int = Field(default=0, description="调用次数")

    def incr_call_count(self) -> None:
        """调用次数自增"""
        self.call_count += 1

    @classmethod
    def create(cls, thread_name: str = None) -> "MonitorData":
        """
        类方法：创建 MonitorData 初始对象
        :param thread_name: 可选，指定线程名
        :return: 初始化完成的 MonitorData 实例
        """
        # 若未传线程名，自动获取当前运行线程的名称（核心简化逻辑）
        if thread_name is None:
            thread_name = threading.current_thread().name
        # 调用类的构造方法，返回初始化对象
        return cls(thread_name=thread_name)


def singleton(wrapped_cls):
    """
    单例装饰器，用于确保一个类只有一个实例，支持继承。
    :return:
    """
    # 这三个容器形成一个最小状态机：实例缓存、初始化标记、监控数据
    _instances: dict[type, Any] = {}
    _initialized: set[type] = set()
    _lock = threading.Lock()
    _monitor: dict[type, MonitorData] = {}

    def _release_instance_resources(instance: Any) -> str | None:
        """显式资源释放入口：优先 close/dispose。"""
        for method_name in ("close", "dispose"):
            method = getattr(instance, method_name, None)
            if callable(method):
                method()
                return method_name
        return None

    class SingletonWrapper(wrapped_cls):
        def __new__(cls, *args, **kwargs):
            with _lock:
                if cls not in _instances:
                    # 双重检查锁：避免并发下重复创建实例
                    _instances[cls] = super(SingletonWrapper, cls).__new__(cls)
                    _monitor[cls] = MonitorData.create()
                    logger.debug(f"[{cls.__name__}] singleton instance created.")

                # 计数写操作在锁内完成，避免并发自增丢失
                if cls in _monitor:
                    _monitor[cls].incr_call_count()
                return _instances[cls]

        def __init__(self, *args, **kwargs):
            cls = type(self)
            if cls in _initialized:
                return
            with _lock:
                # __new__ 每次都会返回实例，这里确保 __init__ 只真正执行一次
                if cls in _initialized:
                    return
                super(SingletonWrapper, self).__init__(*args, **kwargs)
                _initialized.add(cls)

        @classmethod
        def monitor_info(cls) -> dict[str, Any]:
            """获取单例的监控信息"""
            if cls in _monitor:
                return {
                    "class_name": cls.__name__,
                    **_monitor[cls].model_dump(),
                }
            return {}

        @classmethod
        def destroy(cls) -> None:
            """销毁单例实例并清空该类监控数据。"""
            with _lock:
                if cls in _instances:
                    instance = _instances[cls]
                    release_method = None
                    try:
                        release_method = _release_instance_resources(instance)
                    except Exception:
                        logger.exception(f"[{cls.__name__}] singleton resource release failed.")

                    del _instances[cls]
                    # 删除初始化标记后，下一次调用会重新执行 __init__
                    _initialized.discard(cls)
                    logger.debug(
                        f"[{cls.__name__}] singleton instance destroyed. "
                        f"release_method={release_method or 'none'}"
                    )

                if cls in _monitor:
                    del _monitor[cls]

    SingletonWrapper.__name__ = wrapped_cls.__name__
    SingletonWrapper.__doc__ = wrapped_cls.__doc__
    SingletonWrapper.__module__ = wrapped_cls.__module__
    SingletonWrapper.__orig_class__ = wrapped_cls

    return SingletonWrapper
