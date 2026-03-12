import argparse
from argparse import Namespace
from typing import Any

from pydantic import BaseModel, Field


class Argument(BaseModel):
    arg_prefix: str = Field(default="--", description="参数前缀")
    arg_name: str = Field(..., description="参数名称")
    arg_type: type = Field(default=str, description="参数类型")
    required: bool = Field(default=True, description="是否为必选参数")
    default_val: Any = Field(default=None, description="参数默认值")
    current_val: Any = Field(default=None, description="参数当前值")
    help: str = Field(default=None, description="参数帮助信息")

    @property
    def arg_name_with_prefix(self) -> str:
        return f"{self.arg_prefix}{self.arg_name}"


class Argparser:
    """
    命令行参数解析器
    """

    def __init__(self, desc: str = None):
        self.parser = argparse.ArgumentParser(description=desc or "Command line arguments parser")
        # {name_with_prefix: Argument}
        self.args: dict[str, Argument] = dict()
        # list[{name: prefix}]
        self.args_with_prefix: list[dict[str, str]] = list()

    def add_arg(self, arg: Argument):
        """
        添加参数
        """
        arg_name_with_prefix = f"{arg.arg_prefix + arg.arg_name}"
        self.parser.add_argument(
            arg_name_with_prefix,
            type=arg.arg_type,
            required=arg.required,
            help=arg.help
        )
        self.args[arg_name_with_prefix] = arg
        self.args_with_prefix.append({arg.arg_name: arg.arg_prefix})

    def add_args(self, args: list[Argument]):
        """
        批量添加参数
        """
        for arg in args:
            self.add_arg(arg)

    def get_arg(self, arg_name_with_prefix: str, argv: list[str] | None = None) -> Argument | None:
        """
        获取参数
        """
        args = self.list_args(argv=argv)
        for arg in args:
            if arg.arg_name_with_prefix == arg_name_with_prefix:
                return arg
        return None

    def parse(self, argv: list[str] | None = None) -> Namespace:
        """
        解析参数
        """
        return self.parser.parse_args(args=argv)

    def list_args(self, argv: list[str] | None = None) -> list[Argument]:
        """
        列出所有参数
        :param argv: 命令行参数
        """
        namespace = self.parse(argv)
        args_dict = vars(namespace)
        for param_name, param_value in args_dict.items():
            item = next((item for item in self.args_with_prefix if param_name in item), None)
            assert item is not None, f"Cannot find information for parameter {param_name}"
            # 拼接带前缀的参数名（如 "--path"）
            arg_name_with_prefix = f"{item[param_name]}{param_name}"
            # 找到对应的 Argument 对象，并赋值 current_val
            if arg_name_with_prefix in self.args:
                self.args[arg_name_with_prefix].current_val = param_value
        # 返回所有 Argument 对象的列表
        return list(self.args.values())