import shlex
import subprocess

import requests
from requests import RequestException

from agile.agent.tools.base_structured_tools import BaseStructuredTools
from agile.agent.tools.tool_decorators import structured_tool
from agile.agent.tools.tool_response import ToolCommonResponse


class CommExecutiveCapacityTools(BaseStructuredTools):
    """
    通用执行能力工具集
    """

    def __init__(self):
        super().__init__()

    @structured_tool
    def fetch_url(self, url, method='GET', headers=None, params=None, data=None, timeout=10, verify=True) -> ToolCommonResponse:
        """
        通用的 URL 请求函数
        :param url: 请求的目标 URL（必须）
        :param method: 请求方法（可选，默认 GET，支持 GET/POST/PUT/DELETE 等）
        :param headers: 请求头（可选，默认 None）
        :param params: URL 查询参数（可选，默认 None）
        :param data: POST 表单数据（可选，默认 None）
        :param timeout: 请求超时时间（秒）（可选，默认 10 秒）
        :param verify: 是否验证 SSL 证书（可选，默认 False）
        :return: 包含响应状态、数据、状态码的结果字典
        """
        # 默认请求头（模拟浏览器，避免被反爬拦截）
        default_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

        # 合并自定义请求头和默认请求头
        if headers:
            default_headers.update(headers)

        response = None
        try:
            # 发送请求
            response = requests.request(
                method=method.upper(),
                url=url,
                headers=default_headers,
                params=params,
                data=data,
                timeout=timeout,
                verify=verify
            )

            # 检查响应状态码（200-299 为成功）
            response.raise_for_status()

            # 返回成功结果
            return ToolCommonResponse(
                succeed=True,
                data={
                    'status_code': response.status_code,
                    'text': response.text,
                    'content': response.content,
                    'json': None if not response.headers.get('content-type', '').startswith('application/json') else response.json(),
                    'headers': dict(response.headers)
                }
            )
        except RequestException as e:
            # 捕获所有 requests 异常（网络错误、超时、状态码错误等）
            return ToolCommonResponse(
                succeed=False,
                message=str(e),
                data={
                    "status_code": response.status_code if response else None
                }
            )

    @structured_tool
    def run_command(self, command: str, timeout: int = 10) -> ToolCommonResponse:
        """
        安全执行命令行指令，仅支持单条简单命令，不允许管道、重定向、子命令等危险操作。
        :param command: 需要执行的命令字符串（必须，如 'ls -l'）
        :param timeout: 超时时间（秒）（可选，默认 10 秒）
        :return: 包含 stdout、stderr、exit_code
        """
        # 禁止危险字符，防止注入
        forbidden = [';', '&&', '|', '>', '<', '$(', '`', '\\n']
        if any(x in command for x in forbidden):
            return ToolCommonResponse(
                succeed=False,
                message="The command contains dangerous characters and cannot be executed."
            )
        try:
            args = shlex.split(command)
            result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
            return ToolCommonResponse(
                succeed=result.returncode == 0,
                data={
                    "stdout": result.stdout.strip(),
                    "stderr": result.stderr.strip(),
                    "exit_code": result.returncode
                }
            )
        except subprocess.TimeoutExpired:
            return ToolCommonResponse(
                succeed=False,
                message="The command timed out."
            )
        except Exception as e:
            return ToolCommonResponse(
                succeed=False,
                message=str(e),
            )
