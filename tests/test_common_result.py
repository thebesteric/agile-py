from http import HTTPStatus

from agile_commons.web.common_result import R


class DummyResponse:
    def __init__(self):
        self.status_code = None


def test_success_basic():
    r = R.success()
    assert r.succeed is True
    assert r.code == HTTPStatus.OK.value
    assert r.http_status == HTTPStatus.OK
    assert r.message == HTTPStatus.OK.phrase
    assert r.data is None


def test_error_basic():
    r = R.error()
    assert r.succeed is False
    assert r.code == HTTPStatus.INTERNAL_SERVER_ERROR.value
    assert r.http_status == HTTPStatus.INTERNAL_SERVER_ERROR
    assert r.message == HTTPStatus.INTERNAL_SERVER_ERROR.phrase
    assert r.data is None


def test_success_with_custom_values():
    r = R.success(code=201, message="Created", data={"id": 1}, http_status=HTTPStatus.CREATED)
    assert r.succeed is True
    assert r.code == 201
    assert r.http_status == HTTPStatus.CREATED
    assert r.message == "Created"
    assert r.data == {"id": 1}


def test_error_with_custom_values():
    r = R.error(code=404, message="Not Found", data={"missing": True}, http_status=HTTPStatus.NOT_FOUND)
    assert r.succeed is False
    assert r.code == 404
    assert r.http_status == HTTPStatus.NOT_FOUND
    assert r.message == "Not Found"
    assert r.data == {"missing": True}


def test_chain_methods():
    r = R.build(is_success=True) \
        .set_code(200) \
        .set_message("OK") \
        .set_data({"k": "v"}) \
        .set_track_id("trace-123") \
        .set_http_status(HTTPStatus.OK)
    assert r.succeed is True
    assert r.code == 200
    assert r.message == "OK"
    assert r.data == {"k": "v"}
    assert r.track_id == "trace-123"
    assert r.http_status == HTTPStatus.OK


def test_set_http_status_writes_response():
    r = R.success()
    resp = DummyResponse()
    r.set_http_status(HTTPStatus.ACCEPTED, response=resp)
    assert r.http_status == HTTPStatus.ACCEPTED
    assert resp.status_code == HTTPStatus.ACCEPTED.value


def test_set_http_status_without_value_keeps_existing():
    r = R.success(http_status=HTTPStatus.OK)
    resp = DummyResponse()
    r.set_http_status(None, response=resp)
    assert r.http_status == HTTPStatus.OK
    # 根据当前实现，即便传入 None，也会将已有 http_status 写入 response
    assert resp.status_code == HTTPStatus.OK.value


def test_extract_data_success():
    r = R.success(data={"token": "abc"})
    out = R.extract_data(r, default_value={"token": "default"})
    assert out == {"token": "abc"}


def test_extract_data_default_on_failure():
    r1 = R.error(data={"err": 1})
    out1 = R.extract_data(r1, default_value={"fallback": True})
    assert out1 == {"fallback": True}

    r2 = None
    out2 = R.extract_data(r2, default_value=0)
    assert out2 == 0

    r3 = R.build(is_success=True).set_code(400).set_data("x")
    out3 = R.extract_data(r3, default_value="d")
    assert out3 == "d"


def test_model_dump_structure():
    r = R.success(data={"name": "world"}).set_track_id("tid-1")
    dumped = r.model_dump()
    assert dumped["succeed"] is True
    assert dumped["code"] == HTTPStatus.OK.value
    assert dumped["message"] == HTTPStatus.OK.phrase
    assert dumped["data"] == {"name": "world"}
    assert dumped["http_status"] == HTTPStatus.OK
    assert dumped["track_id"] == "tid-1"
