import json
from typing import Any

from agile.commons.enum import LabeledStrEnum


class ErrorCode(LabeledStrEnum):
    """
    业务错误码枚举（规范完整版）
    """

    # --------------------------
    # 1xxxx 客户端通用错误
    # --------------------------
    BAD_REQUEST = ("10000", "请求不合法")
    VALIDATION_FAILED = ("10001", "参数校验失败")
    PARAM_REQUIRED = ("10002", "缺少必填参数")
    PARAM_TYPE_ERROR = ("10003", "参数类型错误")
    PARAM_VALUE_INVALID = ("10004", "参数值不合法")
    BODY_PARSE_ERROR = ("10005", "请求体解析失败")
    URL_NOT_FOUND = ("10006", "接口不存在")
    METHOD_NOT_ALLOWED = ("10007", "请求方法不支持")

    # --------------------------
    # 2xxxx 认证与权限
    # --------------------------
    UNAUTHORIZED = ("20001", "未登录或登录已过期")
    IDENTITY_INVALID = ("20002", "身份凭证无效")
    IDENTITY_EXPIRED = ("20003", "身份凭证已过期")
    FORBIDDEN = ("20004", "权限不足")
    OPERATION_DENIED = ("20005", "操作被拒绝")

    # --------------------------
    # 3xxxx 数据与资源
    # --------------------------
    RESOURCE_NOT_FOUND = ("30001", "资源不存在")
    RESOURCE_EXISTS = ("30002", "资源已存在")
    RESOURCE_CONFLICT = ("30003", "资源冲突")
    RESOURCE_LOCKED = ("30004", "资源被锁定")
    DATA_STATE_ERROR = ("30005", "数据状态异常")

    # --------------------------
    # 4xxxx 业务操作
    # --------------------------
    OPERATION_FAILED = ("40001", "业务操作失败")
    OPERATION_FREQUENT = ("40002", "操作过于频繁")
    INVALID_STATUS = ("40003", "当前状态不允许此操作")
    LIMIT_EXCEEDED = ("40004", "超出限制")

    # --------------------------
    # 5xxxx 服务端内部错误
    # --------------------------
    SERVER_ERROR = ("50001", "服务器异常")
    DATABASE_ERROR = ("50002", "数据操作异常")
    CACHE_ERROR = ("50003", "缓存服务异常")
    TASK_EXECUTION_ERROR = ("50004", "任务执行失败")
    DEPENDENCY_ERROR = ("50005", "内部依赖异常")

    # --------------------------
    # 6xxxx 第三方服务
    # --------------------------
    THIRD_PARTY_ERROR = ("60001", "第三方服务异常")
    API_REQUEST_FAILED = ("60002", "外部接口调用失败")
    API_RESPONSE_ERROR = ("60003", "外部接口返回异常")

    # --------------------------
    # 9xxxx 其他
    # --------------------------
    UNKNOWN_ERROR = ("99999", "未知错误")


class BizError(Exception):
    """
    业务异常基类
    """

    DEFAULT_CODE = ErrorCode.UNKNOWN_ERROR

    error_code: ErrorCode | None
    code: str
    message: str
    data: dict[str, Any]
    module: str | None
    cause: BaseException | None

    def __init__(
            self,
            *,
            error_code: ErrorCode | int | str | None = None,
            message: str | None = None,
            data: dict[str, Any] | None = None,
            module: str | None = None,
            cause: BaseException | None = None,
    ):
        resolved_enum, resolved_code = self._resolve_error_code(error_code)

        self.error_code = resolved_enum
        self.code = resolved_code
        self.message = message if message is not None else (
            resolved_enum.label if resolved_enum is not None else self.DEFAULT_CODE.label
        )
        self.data = dict(data) if data else {}
        self.module = module
        self.cause = cause

        super().__init__(self.message)

    @classmethod
    def _resolve_error_code(
            cls,
            error_code: ErrorCode | int | str | None
    ) -> tuple[ErrorCode | None, str]:
        if error_code is None:
            return cls.DEFAULT_CODE, cls.DEFAULT_CODE.value

        if isinstance(error_code, ErrorCode):
            return error_code, error_code.value

        if isinstance(error_code, int):
            code = str(error_code)
            matched = ErrorCode.from_value(code)
            return matched, code

        code = error_code.strip()
        if not code:
            return cls.DEFAULT_CODE, cls.DEFAULT_CODE.value

        matched_by_value = ErrorCode.from_value(code)
        if matched_by_value is not None:
            return matched_by_value, matched_by_value.value

        matched_by_name = ErrorCode.from_name(code)
        if matched_by_name is not None:
            return matched_by_name, matched_by_name.value

        return None, code

    @classmethod
    def from_error_code(
            cls,
            error_code: ErrorCode | int | str,
            *,
            message: str | None = None,
            data: dict[str, Any] | None = None,
            module: str | None = None,
            cause: BaseException | None = None,
    ) -> "BizError":
        return cls(
            error_code=error_code,
            message=message,
            data=data,
            module=module,
            cause=cause,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "module": self.module,
            "data": self.data,
            "error_name": self.error_code.name if self.error_code else None,
        }

    def with_data(self, data: dict[str, Any]) -> "BizError":
        self.data = dict(data)
        return self

    def with_module(self, module: str) -> "BizError":
        self.module = module
        return self

    def with_message(self, message: str) -> "BizError":
        self.message = message
        self.args = (message,)
        return self

    def __str__(self):
        code_name = self.error_code.name if self.error_code else "UNKNOWN"
        parts = [
            f"code={self.code}",
            f"name={code_name}",
            f"message={self.message}",
        ]

        if self.module:
            parts.append(f"module={self.module}")

        if self.data:
            try:
                data_json = json.dumps(self.data, ensure_ascii=False, separators=(",", ":"), default=str)
            except (TypeError, ValueError):
                data_json = str(self.data)
            parts.append(f"data={data_json}")

        return f"BizError({', '.join(parts)})"