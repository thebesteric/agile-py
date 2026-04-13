from collections.abc import Hashable
from typing import Any, Optional, TypeVar, Union, get_args
import threading
import time

from cachetools import TTLCache, LRUCache

from agile.cache import BaseCache
from agile.utils import LogHelper, TimeUnit

logger = LogHelper.get_logger()

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")
D = TypeVar("D")


class MemoryCache(BaseCache[K, V]):
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
            strict_types: bool = False,
    ) -> None:
        super().__init__(default_ttl=default_ttl, time_unit=time_unit)
        self._lock = threading.RLock()
        self._strict_types = strict_types
        self._key_type: type[Any] | None = None
        self._value_type: type[Any] | None = None
        # 如果配置了默认 TTL，则创建具有该 ttl 的 TTLCache，否则使用 LRUCache
        if self._default_ttl is None:
            # 无 TTL：仅使用 LRU 驱逐
            self._cache: Union[LRUCache, TTLCache] = LRUCache(maxsize=maxsize)
        else:
            # 使用 TTLCache 创建实例
            self._cache: TTLCache = TTLCache(maxsize=maxsize, ttl=self._default_ttl)

    def _resolve_types_from_generic(self) -> tuple[type[Any] | None, type[Any] | None]:
        origin_type = getattr(self, "__orig_class__", None)
        if origin_type is None:
            return None, None
        args = get_args(origin_type)
        if len(args) != 2:
            return None, None
        key_type, value_type = args
        resolved_key_type = key_type if isinstance(key_type, type) else None
        resolved_value_type = value_type if isinstance(value_type, type) else None
        return resolved_key_type, resolved_value_type

    @staticmethod
    def _format_type_error(field: str, expected: str, actual_type: type[Any], key: Any, value: Any) -> TypeError:
        return TypeError(
            f"Type validation failed: field={field}, expected={expected}, actual={actual_type.__name__}, "
            f"key={key!r}, value={value!r}"
        )

    def _validate_types(self, key: K, value: V) -> None:
        if not self._strict_types:
            return
        if not isinstance(key, Hashable):
            raise self._format_type_error(
                field="key",
                expected="Hashable",
                actual_type=type(key),
                key=key,
                value=value,
            )

        if self._key_type is None or self._value_type is None:
            resolved_key_type, resolved_value_type = self._resolve_types_from_generic()
            self._key_type = self._key_type or resolved_key_type
            self._value_type = self._value_type or resolved_value_type

        key_type = self._key_type
        if key_type is not None and not isinstance(key, key_type):
            raise self._format_type_error(
                field="key",
                expected=key_type.__name__,
                actual_type=type(key),
                key=key,
                value=value,
            )

        if self._value_type is None:
            self._value_type = type(value)
        value_type = self._value_type
        if value_type is None:
            return
        if not isinstance(value, value_type):
            raise self._format_type_error(
                field="value",
                expected=value_type.__name__,
                actual_type=type(value),
                key=key,
                value=value,
            )

    def _resolve_entry(self, key: K, entry: Any, default: D | None = None) -> tuple[bool, V | D | None]:
        # 兼容两种存储形式：直接值（TTLCache 默认路径）和 (value, expiry) 包装值。
        if isinstance(entry, tuple) and len(entry) == 2:
            value, expiry = entry
            if expiry is None or time.time() <= expiry:
                return False, value
            try:
                del self._cache[key]
            except Exception as ex:
                logger.warning("Failed to delete expired cache entry for key '%s': %s", key, ex)
            return True, default
        return False, entry

    def set(
            self,
            key: K,
            value: V,
            ttl: Optional[Union[int, float]] = None,
            time_unit: TimeUnit = TimeUnit.SECONDS,
    ) -> None:
        """
        设置一个带可选每项 ttl 的值
        """
        with self._lock:
            self._validate_types(key, value)
            # 如果底层是 TTLCache 且 ttl 与默认值相同，直接设置（TTLCache 会自动处理过期）
            resolved_ttl = self._resolve_ttl(ttl, time_unit)
            if isinstance(self._cache, TTLCache) and (ttl is None or resolved_ttl == self._default_ttl):
                self._cache[key] = value
                return

            # 对于 LRUCache 或使用每项 ttl 时，存储包装器 (value, expiry)
            # expiry == None 表示不过期
            expiry = self._expiry_timestamp(ttl, time_unit)
            self._cache[key] = (value, expiry)

    def get(self, key: K, default: D | None = None) -> V | D | None:
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

            _, value = self._resolve_entry(key, entry, default)
            return value

    def delete(self, key: K) -> None:
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

    def items(self) -> list[tuple[K, V]]:
        """
        返回缓存中所有 (key, value) 对的可迭代对象
        :return: Iterable[Tuple[str, Any]]
        """
        with self._lock:
            result: list[tuple[K, V]] = []
            for k, entry in list(self._cache.items()):
                expired, value = self._resolve_entry(k, entry, default=None)
                if not expired:
                    result.append((k, value))
            return result

    def keys(self) -> list[K]:
        """
        返回缓存中所有 key 的可迭代对象
        :return: Iterable[str]
        """
        with self._lock:
            return [k for k, _ in self.items()]

    def values(self) -> list[V]:
        """
        返回缓存中所有 value 的可迭代对象
        :return: Iterable[Any]
        """
        with self._lock:
            return [v for _, v in self.items()]