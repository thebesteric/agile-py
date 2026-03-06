from typing import Optional
import typer

agile_shell_name = "agile"
agile_shell = typer.Typer(
    name=agile_shell_name,
    help=f"""
    这是你的 Agile 的命令行工具 🚀
    核心功能：
    1. 演示如何通过 Typer 提供清晰的帮助文档
    2. 展示自定义函数的使用方式
    3. 支持子命令和参数说明

    示例用法：
    $ {agile_shell_name} greet --name 张三
    """,
    no_args_is_help=True,
    add_completion=False,
)


@agile_shell.command(
    name="greet",
    help="向指定用户打招呼（基础示例命令）",
    short_help="打招呼"
)
def greet(
        name: str = typer.Option(
            ...,
            "--name", "-n",
            help="要打招呼的用户名，例如：张三、李四",
            prompt="请输入用户名"
        ),
        is_formal: Optional[bool] = typer.Option(
            False,
            "--formal", "-f",
            help="是否使用正式的问候语（默认：非正式）"
        )
):
    if is_formal:
        typer.echo(f"尊敬的 {name} 先生/女士，您好。🙂")
    else:
        typer.echo(f"你好，{name} 😜")


# 主入口
def main():
    agile_shell()


if __name__ == "__main__":
    main()
