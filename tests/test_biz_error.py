import unittest

from agile.commons.biz_error import BizError, ErrorCode


class TestBizError(unittest.TestCase):

    def test_default_init(self):
        err = BizError()
        assert err.code == ErrorCode.UNKNOWN_ERROR.value
        assert err.error_code == ErrorCode.UNKNOWN_ERROR
        assert err.message == ErrorCode.UNKNOWN_ERROR.label
        assert err.data == {}
        assert str(err) == (
            f"BizError(code={ErrorCode.UNKNOWN_ERROR.value}, "
            f"name={ErrorCode.UNKNOWN_ERROR.name}, "
            f"message={ErrorCode.UNKNOWN_ERROR.label})"
        )

    def test_init_with_enum_and_custom_message(self):
        err = BizError(error_code=ErrorCode.BAD_REQUEST, message="参数异常")
        assert err.code == ErrorCode.BAD_REQUEST.value
        assert err.error_code == ErrorCode.BAD_REQUEST
        assert err.message == "参数异常"

    def test_init_with_code_value_and_name(self):
        err_by_value = BizError(error_code="10006")
        assert err_by_value.code == ErrorCode.URL_NOT_FOUND.value
        assert err_by_value.error_code == ErrorCode.URL_NOT_FOUND
        assert err_by_value.message == ErrorCode.URL_NOT_FOUND.label

        err_by_name = BizError(error_code="URL_NOT_FOUND")
        assert err_by_name.code == ErrorCode.URL_NOT_FOUND.value
        assert err_by_name.error_code == ErrorCode.URL_NOT_FOUND
        assert err_by_name.message == ErrorCode.URL_NOT_FOUND.label

    def test_init_with_unknown_code_falls_back_to_default_message(self):
        err = BizError(error_code="77777")
        assert err.code == "77777"
        assert err.error_code is None
        assert err.message == ErrorCode.UNKNOWN_ERROR.label

    def test_chain_methods_and_to_dict(self):
        err = (
            BizError(error_code=ErrorCode.OPERATION_FAILED)
            .with_module("order")
            .with_data({"order_id": 1})
            .with_message("创建订单失败")
        )
        dumped = err.to_dict()
        assert dumped["code"] == ErrorCode.OPERATION_FAILED.value
        assert dumped["message"] == "创建订单失败"
        assert dumped["module"] == "order"
        assert dumped["data"] == {"order_id": 1}
        assert dumped["error_name"] == ErrorCode.OPERATION_FAILED.name

    def test_str_does_not_fail_for_non_json_data(self):
        err = BizError(error_code=ErrorCode.SERVER_ERROR, data={"obj": object()})
        out = str(err)
        assert out.startswith(
            f"BizError(code={ErrorCode.SERVER_ERROR.value}, name={ErrorCode.SERVER_ERROR.name}, "
            f"message={ErrorCode.SERVER_ERROR.label}"
        )
        assert "data=" in out

    def test_from_error_code_factory(self):
        err = BizError.from_error_code(ErrorCode.FORBIDDEN, module="auth")
        assert err.code == ErrorCode.FORBIDDEN.value
        assert err.module == "auth"


if __name__ == "__main__":
    unittest.main()

