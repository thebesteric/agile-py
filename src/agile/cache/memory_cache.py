from typing import Any, Optional, Union
import threading
import time

from cachetools import TTLCache, LRUCache

from agile.cache import BaseCache
from agile.utils import LogHelper, TimeUnit

logger = LogHelper.get_logger()


class MemoryCache(BaseCache):
    """
    本地缓存实现
    - 如果提供了 maxsize，我们使用 LRU 缓存，并通过包装带有过期时间戳的值来处理可选的每项 TTL
    - 如果提供了 ttl（且设置了 maxsize），我们优先使用 TTLCache，它会自动处理驱逐
    - 如果 ttl 为 None，则项目不会过期（除非在达到 maxsize 时通过 LRU 驱逐）
    """

    def __init__(
            self,
            maxsize: int = 1024,
            default_ttl: Optional[Union[int, float]] = None,
            time_unit: TimeUnit = TimeUnit.SECONDS,
    ) -> None:
        super().__init__(default_ttl=default_ttl, time_unit=time_unit)
        self._lock = threading.RLock()
        # 如果配置了默认 TTL，则创建具有该 ttl 的 TTLCache，否则使用 LRUCache
        if self._default_ttl is None:
            # 无 TTL：仅使用 LRU 驱逐
            self._cache: Union[LRUCache, TTLCache] = LRUCache(maxsize=maxsize)
        else:
            # 使用 TTLCache 创建实例
            self._cache: TTLCache = TTLCache(maxsize=maxsize, ttl=self._default_ttl)

    def set(
            self,
            key: str,
            value: Any,
            ttl: Optional[Union[int, float]] = None,
            time_unit: TimeUnit = TimeUnit.SECONDS,
    ) -> None:
        """
        设置一个带可选每项 ttl 的值
        """
        with self._lock:
            # 如果底层是 TTLCache 且 ttl 与默认值相同，直接设置（TTLCache 会自动处理过期）
            resolved_ttl = self._resolve_ttl(ttl, time_unit)
            if isinstance(self._cache, TTLCache) and (ttl is None or resolved_ttl == self._default_ttl):
                self._cache[key] = value
                return

            # 对于 LRUCache 或使用每项 ttl 时，存储包装器 (value, expiry)
            # expiry == None 表示不过期
            expiry = self._expiry_timestamp(ttl, time_unit)
            self._cache[key] = (value, expiry)

    def get(self, key: str, default: Any = None) -> Any:
        """
        检索值
        如果我们存储了包装的 (value, expiry)，检查过期时间并在过期时返回默认值。
        对于直接设置的 TTLCache 条目，直接返回它们（TTLCache 会自动过期）。
        """
        with self._lock:
            try:
                entry = self._cache[key]
            except KeyError:
                return default

            # 如果条目是包装的 (value, expiry) 元组，则进行验证
            if isinstance(entry, tuple) and len(entry) == 2:
                value, expiry = entry
                if expiry is None:
                    return value
                if time.time() > expiry:
                    # 已过期：删除并返回默认值
                    try:
                        del self._cache[key]
                    except Exception as ex:
                        logger.warning("Failed to delete expired cache entry for key '%s': %s", key, ex)
                    return default
                return value

            # 否则，直接返回存储的值
            return entry

    def delete(self, key: str) -> None:
        """
        删除指定 key 的缓存项（如果存在）
        :param key: 键
        :return:
        """
        with self._lock:
            try:
                del self._cache[key]
            except KeyError:
                pass

    def clear(self) -> None:
        """
        清空整个缓存
        :return:
        """
        with self._lock:
            self._cache.clear()

    def size(self) -> int:
        """
        获取当前缓存中的项数
        :return:
        """
        with self._lock:
            return len(self._cache)

    def items(self) -> list[tuple[str, Any]]:
        """
        返回缓存中所有 (key, value) 对的可迭代对象
        :return: Iterable[Tuple[str, Any]]
        """
        with self._lock:
            if isinstance(self._cache, TTLCache):
                # TTLCache 自动处理过期
                return list(self._cache.items())
            else:
                # LRUCache 需手动处理过期
                now = time.time()
                result = []
                keys_to_delete = []
                for k, (v, expiry) in self._cache.items():
                    if expiry is None or now <= expiry:
                        result.append((k, v))
                    else:
                        keys_to_delete.append(k)
                # 清理过期项
                for k in keys_to_delete:
                    del self._cache[k]
                return result

    def keys(self) -> list[str]:
        """
        返回缓存中所有 key 的可迭代对象
        :return: Iterable[str]
        """
        with self._lock:
            if isinstance(self._cache, TTLCache):
                return list(self._cache.keys())
            else:
                now = time.time()
                keys = []
                keys_to_delete = []
                for k, (v, expiry) in self._cache.items():
                    if expiry is None or now <= expiry:
                        keys.append(k)
                    else:
                        keys_to_delete.append(k)
                for k in keys_to_delete:
                    del self._cache[k]
                return keys

    def values(self) -> list[Any]:
        """
        返回缓存中所有 value 的可迭代对象
        :return: Iterable[Any]
        """
        with self._lock:
            if isinstance(self._cache, TTLCache):
                return list(self._cache.values())
            else:
                now = time.time()
                values = []
                keys_to_delete = []
                for k, (v, expiry) in self._cache.items():
                    if expiry is None or now <= expiry:
                        values.append(v)
                    else:
                        keys_to_delete.append(k)
                for k in keys_to_delete:
                    del self._cache[k]
                return values

