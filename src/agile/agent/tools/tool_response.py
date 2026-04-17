from typing import Any

from pydantic import BaseModel, Field, model_validator


class ToolCommonResponse(BaseModel):
    data: list[Any] | dict[str, Any] | None = Field(default=None, description="结果数据")
    message: str | None = Field(default=None, description="消息")
    succeed: bool = Field(default=True, description="是否成功")
    metadata: dict[str, Any] | None = Field(default=None, description="元数据")

    @model_validator(mode="after")
    def set_default_message(self) -> "ToolCommonResponse":
        if self.message is None:
            self.message = "Execution successful" if self.succeed else "Execution failed"
        return self