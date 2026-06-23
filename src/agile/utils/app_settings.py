import uuid
from typing import Literal, Any, Callable

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):

    @classmethod
    def get_env_prefix(cls) -> str:
        """环境变量统一前缀"""
        return ""

    @classmethod
    def get_nested_delimiter(cls) -> str:
        """嵌套配置分隔符"""
        return "__"

    @classmethod
    def get_env_file_list(cls) -> list[str]:
        """默认加载的环境文件"""
        return [".env", ".env.local", ".env.dev", ".env.test", ".env.staging", ".env.prod"]

    @classmethod
    def get_case_sensitive(cls) -> bool:
        """是否忽略大小写"""
        return True

    @classmethod
    def get_extra_policy(cls) -> Literal["ignore", "forbid", "allow"]:
        """
        可重写：多余字段处理策略
        ignore: 忽略未知环境变量（默认）
        forbid: 存在未知字段直接抛校验异常
        allow: 保留未知字段到实例
        """
        return "ignore"

    @classmethod
    def build_model_config(cls) -> SettingsConfigDict:
        """配置模型行为"""
        return SettingsConfigDict(
            env_file_encoding="utf-8",
            env_file=cls.get_env_file_list(),
            env_prefix=cls.get_env_prefix(),
            case_sensitive=cls.get_case_sensitive(),
            env_nested_delimiter=cls.get_nested_delimiter(),
            extra=cls.get_extra_policy(),
        )

    @staticmethod
    def env_field(
            # 环境变量名称
            alias: str | None = None,
            *,
            # 默认值
            default: Any = ...,
            # 动态默认值工厂（与 default 互斥）
            default_factory: Callable[[], Any] | Callable[[dict[str, Any]], Any] | None = None,
            # 其余自定义 Field 参数
            **kwargs,
    ) -> Any:
        """
        环境变量专用 Field 封装
        :param default: 默认值，不传 = ... 代表该环境变量必填
        :param alias: 环境变量名称
        :param default_factory: 无参函数，动态生成默认值，和 default 不能同时使用
        :param kwargs: 透传其余 Field 原生参数
        """
        # 互斥校验：default 和 default_factory 不能同时提供
        if default is not ... and default_factory is not None:
            raise ValueError("default and default_factory cannot be used together")

        if alias is not None:
            kwargs["alias"] = alias
        if default is not ...:
            kwargs["default"] = default
        if default_factory is not None:
            kwargs["default_factory"] = default_factory

        return Field(**kwargs)

    def __init_subclass__(cls, **kwargs):
        """子类自动注入 model_config，无需手动声明"""
        super().__init_subclass__(**kwargs)
        cls.model_config = cls.build_model_config()
