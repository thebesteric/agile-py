# Agile 使用手册

Agile 是面向 Python 应用开发的通用工具包，提供配置管理、日志、缓存、业务模型、调用观测、文本检索、Milvus 向量存储以及 LangChain 工具注册等能力。它不是完整的 Web 框架或 Agent 平台，可以按模块引入脚本、后端服务、数据处理任务和 RAG 应用。

本文以**当前工作区源码**为准；`pyproject.toml` 中包版本为 **0.1.23**，要求 **Python >= 3.12、< 4.0**。工作区新增能力不代表已发布到同版本包仓库，使用本文全部功能建议从本仓库安装。

## 目录

- [1. 能力总览](#1-能力总览)
- [2. 安装与运行](#2-安装与运行)
- [3. 五分钟上手](#3-五分钟上手)
- [4. 环境变量与应用配置](#4-环境变量与应用配置)
- [5. 能力清单](#5-能力清单)
  - [5.1 日志管理](#51-日志管理)
  - [5.2 缓存与时间单位](#52-缓存与时间单位)
  - [5.3 函数计时与调用记录](#53-函数计时与调用记录)
  - [5.4 单例初始化任务与字符串构建](#54-单例初始化任务与字符串构建)
  - [5.5 模型增强枚举与业务异常](#55-模型增强枚举与业务异常)
  - [5.6 Web 响应与分页](#56-web-响应与分页)
  - [5.7 中英文时间提取](#57-中英文时间提取)
  - [5.8 BM25 全文检索](#58-bm25-全文检索)
  - [5.9 向量模型与 Milvus](#59-向量模型与-milvus)
  - [5.10 Agent 结构化工具](#510-agent-结构化工具)
  - [5.11 命令行能力](#511-命令行能力)
- [6. 综合案例](#6-综合案例)
- [7. 开发测试与常见问题](#7-开发测试与常见问题)
- [8. 源码导航与许可证](#8-源码导航与许可证)

## 1. 能力总览

| 能力 | 主要入口 | 应用场景 |
| --- | --- | --- |
| 环境变量读写 | `agile.utils.EnvHelper` | 加载 `.env`、动态读取配置、自动或显式类型转换 |
| 类型化应用配置 | `agile.utils.app_settings.AppSettings` | 启动校验、统一前缀、嵌套配置、导出环境变量 |
| 日志 | `agile.utils.LogHelper` | 彩色控制台、YAML 配置、文件轮转、业务日志前缀 |
| 本地内存缓存 | `agile.cache.MemoryCache`、`BaseCache` | 热点数据、TTL、LRU、懒加载及缓存回调 |
| 时间单位 | `agile.utils.TimeUnit` | 超时、TTL 和时长换算 |
| 函数计时 | `agile.utils.timing` | 单个同步或异步函数耗时日志 |
| 调用树分析 | `agile.utils.timing.timing_stack` | 入口函数下的调用链性能排查 |
| 调用记录 | `agile.utils.recorder`、`CallRecord` | 操作审计、接口记录、自定义存储回调 |
| 单例 | `agile.utils.singleton` | 共享客户端、资源释放、调用次数监控 |
| 初始化任务 | `agile.utils.task_initializer.TaskInitializer` | 启动注册、延迟初始化、重复加载 |
| 字符串构建 | `agile.utils.string_utils.StringBuilder` | 多段文本拼装、提示词构建 |
| Pydantic 增强 | `agile.utils.pydantic_extension.BaseModelEnhance` | 字典式访问、空字符串处理、自定义校验错误 |
| 标签枚举 | `agile.commons.LabeledStrEnum`、`LabeledIntEnum` | 状态值、下拉选项、提示词选项 |
| 业务异常 | `agile.commons.BizError`、`ErrorCode` | 错误码、异常上下文、异常到响应的转换 |
| Web 响应及分页 | `agile.web.R`、`PagingRequest`、`PagingResponse` | 统一响应、HTTP 状态码、分页计算 |
| 中英文时间解析 | `agile.utils.extract_time_range` 模块 | 将自然语言时间转换为查询条件 |
| BM25 全文检索 | `agile.search.BM25Searcher` | 中文关键词搜索、本地索引、RAG 召回 |
| 向量模型抽象 | `agile.db.vector.BaseEmbedModel` | 自有 Embedding 接入、余弦相似度、Token 计数 |
| Milvus 管理 | `agile.db.vector.MilvusManager` | 集合、索引、写入、搜索、过滤、多集合字段映射 |
| LangChain 检索器 | `agile.db.vector.MilvusRetriever` | 已有类定义，但当前与 Manager 接口未对齐，见第 5.9 节 |
| Agent 工具 | `BaseStructuredTools`、`structured_tool`、`CommExecutiveCapacityTools` | 注册 LangChain 工具、HTTP 请求、简单命令执行 |
| 命令行 | `agile`、`agile.utils.argparser.Argparser` | CLI 演示、自定义脚本参数 |

**功能边界：** `agile.db.kv`、`agile.db.relational` 目前只是空包，不提供 Redis、关系数据库或 ORM；Agile 不内置模型供应商、完整 Agent 编排、认证系统、审计数据库表或 Web 服务。

## 2. 安装与运行

### 2.1 从源码安装

在仓库根目录创建虚拟环境：

```bash
python -m venv .venv
```

Windows PowerShell 激活：

```powershell
.\.venv\Scripts\Activate.ps1
```

Linux / macOS 激活：

```bash
source .venv/bin/activate
```

安装源码：

```bash
python -m pip install -e .
```

项目也提供 Poetry 配置及锁文件，可以改用 `poetry install`。当前未按能力拆分 extras，默认安装包含 LangChain、PyMilvus、NumPy、Whoosh 等全部声明依赖。

### 2.2 使用 uv 安装与运行

uv 方式与上面的 pip / Poetry 方式任选一种即可，无需重复创建环境。以下命令均在仓库根目录执行。

**安装 uv：**

```bash
python -m pip install uv
uv --version
```

**根据锁文件同步项目：**

```bash
uv sync --locked
```

uv 会管理项目根目录的 `.venv` 并以可编辑方式安装 Agile，无需手动激活环境。`--locked` 要求现有 `uv.lock` 与项目声明一致，不自动更新锁文件；如果提示不一致，应先确认依赖变更，再执行 `uv lock` 更新并重新同步。需要指定 Python 版本时，可改用 `uv sync --locked --python 3.12`。

**运行项目命令：**

```bash
uv run --locked agile --help
uv run --locked agile --name 张三
uv run --locked python -c "import agile; print('Agile import OK')"
```

将第 3 节快速上手示例保存为 `quickstart.py` 后，可使用 `uv run --locked python quickstart.py` 运行，无需切换到虚拟环境中的 Python 路径。

**临时补充依赖：**

当前部分能力使用的依赖未直接声明，且 Poetry 的 `[tool.poetry.group.dev.dependencies]` 不是 uv 的 `[dependency-groups]`，不能假设 `uv sync` 会自动安装其中的 `pytest`。可通过 `uv run --with` 为单次运行添加依赖，不修改 `pyproject.toml` 或 `uv.lock`。

运行离线测试：

```bash
uv run --locked --with pytest --with pydantic-settings python -m pytest tests --ignore=tests/test_milvus_manager.py
```

将第 6.1 节综合案例保存为 `app.py` 后，启动 FastAPI 服务：

```bash
uv run --locked --with pydantic-settings --with fastapi --with uvicorn uvicorn app:app --reload
```

其他脚本同样可以追加 `--with python-dotenv`、`--with requests` 等参数，按下一节的依赖表选择。`--locked` 约束项目锁文件，不会把临时 `--with` 依赖写入锁文件；需要可复现的临时依赖版本时应自行指定版本约束。

**注意：** `uv sync` 默认会移除环境中未被项目声明的额外包。若先用 `uv pip install` 手动补装依赖，再执行同步，补装的包可能被移除；临时使用优先采用上述 `--with` 方式，长期依赖应在业务项目中通过 `uv add` 正式声明。仅预览同步结果可执行 `uv sync --locked --dry-run`，不会修改环境或锁文件。

### 2.3 按需补充依赖

以下包由源码直接使用，但尚未在项目直接依赖中完整声明，不应依赖其他包恰好间接安装它们：

| 功能 | 补充安装 |
| --- | --- |
| `AppSettings` | `python -m pip install pydantic-settings` |
| `EnvHelper` | `python -m pip install python-dotenv` |
| 通用 HTTP 执行工具 | `python -m pip install requests` |
| FastAPI 示例（可选） | `python -m pip install fastapi uvicorn` |
| 测试 | `python -m pip install pytest`；普通 pip 安装不会安装 Poetry 开发组 |

Milvus 示例还需要可访问的 Milvus 服务、凭证，以及维度匹配的 Embedding 模型；本文不包含服务部署。

### 2.4 导入约定

常用入口：

```python
from agile.utils import EnvHelper, LogHelper, TimeUnit, recorder, singleton, timing
from agile.cache import MemoryCache
from agile.commons import BizError, ErrorCode, LabeledIntEnum, LabeledStrEnum
from agile.web import PagingRequest, PagingResponse, R
```

其他能力使用完整模块路径，例如 `from agile.utils.app_settings import AppSettings`。后续示例均给出对应导入。

导入 `agile.utils` 时，部分模块会初始化日志，默认配置可能创建项目根目录下的 `logs/`。建议从有 `pyproject.toml`、`.git` 或 `.project-root` 标识的项目目录运行。

## 3. 五分钟上手

**场景：** 查询商品先读缓存，记录耗时和调用结果，返回统一响应。无需 Web 框架和数据库，可直接在仓库根目录运行。

```python
from agile.cache import MemoryCache
from agile.utils import LogHelper, TimeUnit, recorder, timing
from agile.web import R

logger = LogHelper.get_logger("quickstart", title="[商品服务]")
cache = MemoryCache[str, dict](maxsize=100, default_ttl=5, time_unit=TimeUnit.MINUTES)


@recorder(name="查询商品", record_request=False, record_response=False)
@timing(func_name="load_product")
def load_product(product_id: str) -> dict:
    return cache.get_or_set(
        product_id,
        lambda: {"id": product_id, "name": "Agile 使用手册"},
        on_get=lambda key, value: logger.info("缓存命中：%s", key),
        on_set=lambda key, value: logger.info("首次载入：%s", key),
    )


print(R.success(data=load_product("book-001")).model_dump_json())
print(R.success(data=load_product("book-001")).model_dump_json())
```

第一次执行数据工厂，第二次命中缓存。`R.success()` 默认业务码是 **200**，不是 0；`recorder` 默认输出调用记录 JSON，`timing` 输出耗时日志。


## 4. 环境变量与应用配置

### 4.1 EnvHelper：动态读写与类型转换

**场景：** 脚本没有固定配置模型，希望加载 `.env` 并按需读取、转换变量。

```python
from datetime import date

from agile.utils import EnvHelper

env = EnvHelper(env_file_path=".env", override=False)
env.set("DEMO_PORT", 8080)
env.set("DEMO_DEBUG", True)
env.set("DEMO_TAGS", ["rag", "search"])
env.set("DEMO_START_DATE", date(2026, 11, 12))

print(env.get("DEMO_PORT", var_type=int))
print(env.get("DEMO_DEBUG", var_type=bool))
print(env.get("DEMO_TAGS", var_type=list))
print(env.get("DEMO_START_DATE", var_type=date))
print(env.get("DEMO_MISSING", default="fallback"))
print(env.get_required("DEMO_PORT", var_type=int))
```

| 接口 | 用法 |
| --- | --- |
| `EnvHelper(env_file_path=None, override=False, env_mode=None)` | 加载一个环境文件；`override` 决定是否覆盖已有进程环境变量 |
| `get(key, default=None, var_type=None)` | 缺失返回默认值；省略类型时自动推断 |
| `get_required(key, var_type=None)` | 缺失抛出 `KeyError`；存在但为空不等同于缺失 |
| `set(key, value)` | 序列化后写入当前进程的 `os.environ`，**不写回文件** |

**文件加载规则：**

1. 传入 `env_file_path` 时只尝试该路径，不额外合并 `.env`。
2. 未传路径时，从项目根目录尝试 `.env.<env_mode>`，再尝试 `.env`。
3. 模式优先取构造参数，其次取 `ENV_MODE` / `env_mode` 环境变量。
4. **仅加载第一个存在的文件**，不是多文件叠加；默认不覆盖已有进程环境变量。

例如 `EnvHelper(env_mode="prod")` 在 `.env.prod` 存在时不会补读 `.env`。找不到文件会记录警告，仍可读取当前进程的环境变量。

显式类型支持 `str/bool/int/float/list/dict/tuple/set`、`datetime/date/time` 和 `type(None)`。布尔真值包括 `true/1/yes/on/enable`，假值包括 `false/0/no/off/disable`；空值包括 `none/null/nil`，匹配不区分大小写。集合推荐使用 JSON 字符串；日期可用 `2026-11-12`，日期时间可用 `2026-11-12 10:00:00`。

自动推断先识别布尔值再识别整数，因此 `"1"` / `"0"` 会得到布尔值。对端口、ID、编号等字段请显式指定 `var_type=int` 或 `str`。转换失败对外抛出 `TypeError`。

### 4.2 AppSettings：类型化配置

**场景：** 服务有固定配置项，希望启动时完成类型校验、统一前缀并支持嵌套配置。先安装 `pydantic-settings`。

项目根目录的 `.env` 示例：

```dotenv
SHOP_HOST=127.0.0.1
SHOP_PORT=8080
SHOP_DEBUG=true
SHOP_DATABASE__HOST=db.internal
SHOP_DATABASE__PORT=5432
SHOP_TAGS=["api","rag"]
```

```python
from pydantic import BaseModel, Field

from agile.utils.app_settings import AppSettings


class DatabaseSettings(BaseModel):
    host: str = "localhost"
    port: int = 5432


class Settings(AppSettings):
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    tags: list[str] = Field(default_factory=list)
    api_token: str = AppSettings.env_field(alias="SHOP_API_TOKEN", default="", os_env=True)

    @classmethod
    def get_env_prefix(cls) -> str:
        return "SHOP_"

    @classmethod
    def get_env_file_list(cls) -> list[str]:
        return [".env", ".env.local"]


settings = Settings()
print(settings.host, settings.port, settings.database.host)
print(settings.tags)
```

| 可重写方法 | 默认值 | 说明 |
| --- | --- | --- |
| `get_env_prefix()` | `""` | 自动生成别名的前缀 |
| `get_nested_delimiter()` | `"__"` | 嵌套配置分隔符 |
| `get_env_file_list()` | `.env`、`.env.local`、`.env.dev`、`.env.test`、`.env.staging`、`.env.prod` | 按列表读取，后面的文件覆盖前面同名项 |
| `get_case_sensitive()` | `True` | `True` 自动将字段部分映射为大写，`False` 映射为小写；前缀不变 |
| `get_extra_policy()` | `"ignore"` | 未知字段策略：`ignore/forbid/allow` |

一般优先级为：构造参数 > 进程环境变量 > dotenv 文件 > 默认值。文件默认相对于当前工作目录，可用 `Settings(_env_file=".env.prod")` 指定文件，或 `Settings(_env_file=None)` 禁用文件读取。

**与 EnvHelper 不同：** `AppSettings` 默认尝试列表中所有存在的文件，不会按 `ENV_MODE` 自动筛选。生产服务应重写文件列表或显式传 `_env_file`，避免意外加载其他环境配置。

`AppSettings.env_field(...)` 参数：

- `alias`：显式环境变量名，不再自动追加统一前缀。
- `default` / `default_factory`：静态或动态默认值，二者互斥；均未提供则字段必填。
- `os_env=True`：初始化后写入当前进程环境变量，默认仅在变量不存在时写入。
- `os_env_override=True`：配合 `os_env=True` 覆盖已有值。
- 其他参数透传 Pydantic `Field`，例如 `description`、`ge`、`le`。

`get_case_sensitive=False` 不是关闭底层严格匹配：例如前缀 `SHOP_` 和字段 `host` 会生成 `SHOP_host`。显式别名不受此开关影响；Windows 进程环境变量的大小写行为仍受操作系统影响。

## 5. 能力清单

### 5.1 日志管理

**场景：** 统一服务日志格式、为某个业务增加前缀，或通过 YAML 管理控制台和文件输出。

```python
import logging

from agile.utils import LogHelper

logger = LogHelper.get_logger("order-service", title="[订单]")
logger.debug("调试日志")
logger.info("订单创建成功：%s", "order-001")
logger.warning("库存不足")

simple_logger = LogHelper.basic_config(name="simple", level=logging.INFO)
simple_logger.info("使用标准库 basicConfig")
```

- `get_logger(name=None, *, title=None, search_from=None, indicator=None)`：名称省略时从调用模块推断；同名基础 logger 会缓存，`title` 通过适配器添加。
- 默认从 `search_from="."` 向上定位项目根目录，标识包括 `.project-root`、`setup.cfg`、`setup.py`、`.git`、`pyproject.toml`、`agile-logger.yaml`。
- 优先读取根目录 `agile-logger.yaml`，否则读取包内置配置；定位或配置失败时降级到控制台日志。
- YAML 顶层可添加变量，字符串中的 `{变量名}` 会被替换；`log_dir` 的相对路径以项目根目录为基准。
- `basic_config` 直接调用标准库 `logging.basicConfig`，不读取 YAML；已存在日志处理器时遵循标准库行为，必要时自行传 `force=True`。

#### 自定义 YAML

在项目根目录放置以下 `agile-logger.yaml`，可得到控制台与每日轮转文件日志：

```yaml
version: 1
disable_existing_loggers: false
log_dir: "./logs"
app_name: "my-app"
formatters:
  standard:
    format: "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
handlers:
  console:
    class: logging.StreamHandler
    formatter: standard
    stream: ext://sys.stdout
  file:
    class: logging.handlers.TimedRotatingFileHandler
    formatter: standard
    filename: "{log_dir}/{app_name}.log"
    when: midnight
    backupCount: 7
    encoding: utf-8
root:
  level: INFO
  handlers: [console, file]
```

内置配置提供彩色控制台、INFO 及 ERROR 文件 handler，按天保留 7 份。**当前内置两个文件 handler 指向同一个 `agile.log`**，ERROR 及以上记录可能重复写入；需要错误日志分流时请使用自定义配置，将错误文件指定为不同路径。不同名称 logger 首次创建时可能重新应用全局配置，建议在应用启动时统一规划。

### 5.2 缓存与时间单位

#### 5.2.1 MemoryCache：进程内缓存

**场景：** 缓存用户资料、配置快照或昂贵计算，减少重复访问。它不跨进程共享，不是分布式缓存。

```python
from agile.cache import MemoryCache
from agile.utils import TimeUnit

cache = MemoryCache[str, dict](
    maxsize=1024,
    default_ttl=5,
    time_unit=TimeUnit.MINUTES,
    strict_types=True,
)
cache.set("user:1", {"name": "张三"})
cache.set("user:2", {"name": "李四"}, ttl=30, time_unit=TimeUnit.SECONDS)

print(cache.get("user:1"))
print(cache.get("missing", default={}))
print(cache.items(), cache.keys(), cache.values(), cache.size())
cache.delete("user:2")
cache.clear()
```

| 构造参数 | 默认值 | 含义 |
| --- | --- | --- |
| `maxsize` | `1024` | 容量上限，达到上限时按 LRU 淘汰 |
| `default_ttl` | `None` | 默认过期时长；`None` 表示未配置默认过期 |
| `time_unit` | `TimeUnit.SECONDS` | 构造时 TTL 的单位 |
| `strict_types` | `False` | 启用键值类型检查；推荐配合简单泛型如 `MemoryCache[str, dict]` |

`strict_types=True` 时，无法从泛型确定的值类型会由首次写入推断；类型不匹配抛 `TypeError`。它不是递归 Pydantic 校验，不验证字典内部结构。

#### 5.2.2 懒加载与缓存回调

```python
from agile.cache import MemoryCache

cache = MemoryCache[str, dict](maxsize=100)


def load_user() -> dict:
    return {"id": 1, "name": "张三"}


user = cache.get_or_set(
    "user:1",
    load_user,
    ttl=60,
    on_get=lambda key, value: print("命中", key),
    on_set=lambda key, value: print("写入", key),
    emit_get_after_set=False,
)
print(user)
```

`get_or_set(key, value, ttl=None, time_unit=TimeUnit.SECONDS, on_get=None, on_set=None, emit_get_after_set=False)` 可传直接值或无参工厂。仅 miss 时执行工厂和 `on_set`，命中执行 `on_get`；将 `emit_get_after_set` 设为 `True` 可在写入后额外触发 `on_get`。

**当前实现注意事项：**

- `get/set` 等单次操作有锁，但 `get_or_set` 整体不是原子操作；并发 miss 可能重复执行工厂。
- `get_or_set` 将 `None` 当作 miss，不能用它区分“已缓存空值”和“不存在”。
- `set(..., ttl=None)` 表示使用默认 TTL，不是强制永久缓存。需要无过期缓存时，单独创建 `default_ttl=None` 的实例。
- 建议只使用正数 TTL。不要依赖 `0` 或负数表示永久，源码实际未实现这条归一化规则。
- 配置默认 TTL 后底层是 `TTLCache`，单项自定义 TTL 仍受底层默认 TTL 限制，不应依赖它延长默认生命周期；需要不同 TTL 时可用 `default_ttl=None`，逐项设置。
- 自定义过期项采用惰性清理，`size()` 可能暂含未读取的过期项；`items()/keys()/values()` 会检查并过滤。
- 当前实现用二元组包装过期信息，不适合直接缓存任意二元组值；推荐包装为字典或模型。

`BaseCache` 是扩展接口，约定 `set/get/delete/clear/size/items/keys/values`，并提供 `get_or_set` 通用逻辑。自定义后端可继承实现；源码文件名为 `base_cahce.py`，外部优先使用 `from agile.cache import BaseCache`，无需依赖该拼写。

#### 5.2.3 TimeUnit：时间换算

```python
from agile.utils import TimeUnit

print(TimeUnit.MINUTES.to_seconds(5))
print(TimeUnit.SECONDS.convert_to(1.5, TimeUnit.MILLI_SECONDS))
print(TimeUnit.HOURS.convert_to(2, "minutes"))
print(TimeUnit.from_string("ms"))
```

前三项分别为 `300.0`、`1500.0`、`120.0`。支持 `NANO_SECONDS/MICRO_SECONDS/MILLI_SECONDS/SECONDS/MINUTES/HOURS/DAYS`；字符串支持单复数全称、枚举名和 `ns/us/ms/s/sec/m/min/h/hr/d/day`，忽略大小写及首尾空白。未知单位抛 `ValueError`。


### 5.3 函数计时与调用记录

#### 5.3.1 timing：单函数耗时

**场景：** 记录数据库访问、模型调用、批处理函数的耗时，保留原返回值与异常。

```python
import asyncio

from agile.utils import timing


@timing
def calculate_total(price: float, quantity: int) -> float:
    return price * quantity


@timing(func_name="异步加载", log_level="INFO", precision=3)
async def load_data() -> dict:
    await asyncio.sleep(0.01)
    return {"ok": True}


print(calculate_total(12.5, 2))
print(asyncio.run(load_data()))
```

支持 `@timing`、`@timing()`、`@timing(...)`。参数 `func_name` 默认为函数完整限定名；`log_level` 支持 `DEBUG/INFO/WARNING/ERROR/CRITICAL`；`precision` 默认 3。耗时自动按毫秒、秒或分钟显示；异常会记录错误及耗时，然后原样抛出。

#### 5.3.2 timing_stack：调用树耗时

**场景：** 只在业务入口加装饰器，定位内部哪一层调用较慢。

```python
import time

from agile.utils.timing import timing_stack


def read_data():
    time.sleep(0.01)
    return [1, 2, 3]


def transform(data):
    return [value * 2 for value in data]


@timing_stack(
    func_name="数据处理链",
    include="all",
    output_format="text",
    warning_at=5,
    include_patterns="__main__.**",
)
def pipeline():
    return transform(read_data())


print(pipeline())
```

| 参数 | 默认值 | 作用 |
| --- | --- | --- |
| `func_name` | 函数名 | 报告标题 |
| `log_level` / `precision` | `INFO` / `2` | 输出日志级别 / 毫秒小数位 |
| `include` | `"all"` | `inclusive` 含子调用、`exclusive` 自身耗时、`all` 两者 |
| `output_format` | `"text"` | 文本树或 `"json"` |
| `warning_at` | `None` | 超过阈值的节点加标记，单位为**毫秒** |
| `include_patterns` / `exclude_patterns` | `None` | 按函数限定名过滤，可传字符串或字符串集合 |
| `include_protected` / `include_private` / `include_magic` | 均为 `False` | 是否包含受保护、私有及魔术方法 |

模式中 `*` 不跨越点号，`**` 可跨层级。例如 `my_app.**` 表示整个包。示例以脚本方式运行使用 `__main__.**`，导入为模块时请改成实际模块名。同步、异步入口均可装饰；基于 Python profile 钩子跟踪，会引入额外开销，建议用于调试，不应将其视为跨线程、分布式链路或高并发异步任务的完整追踪系统。

#### 5.3.3 recorder：调用审计与自定义存储

**场景：** 记录函数的输入、输出、状态和耗时，业务方决定写日志、文件、队列还是数据库。

```python
from agile.utils import CallRecord, recorder

records: list[CallRecord] = []


@recorder(name="计算总价", callback=records.append)
def total(price: float, quantity: int) -> float:
    return price * quantity


print(total(12.5, 2))
print(records[0].model_dump_json())
```

支持普通函数、实例方法、类方法、静态方法，以及 `def` / `async def`。使用 `@classmethod` 或 `@staticmethod` 时，应放在 `@recorder` 上方。生成器与异步生成器暂不支持，装饰时会抛 `TypeError`。

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `name` | 函数完整限定名 | 记录名称，最多 512 字符 |
| `enable` | `True` | 关闭时直接返回原函数 |
| `callback` | `log_record` | 接收 `CallRecord` 的同步或异步回调 |
| `record_request` | `True` | 记录函数实参及请求信息 |
| `record_response` | `True` | 记录返回值，异常时不记录返回值 |
| `redacted_headers` | `None` | 需要脱敏的 HTTP 请求头名称集合，默认**不脱敏** |

不传回调时，通过标准库 `agile.utils.recorder` logger 以 INFO 输出一条 JSON。应用应配置 handler 与日志级别，例如 `logging.basicConfig(level=logging.INFO)`，或使用 `LogHelper`。

`CallRecord` 字段：

| 字段 | 含义 |
| --- | --- |
| `api_name` / `api_path` / `http_method` | 调用名称、路径及方法；非 HTTP 调用使用函数限定名和 `UNKNOWN` |
| `request_id` / `client_ip` | HTTP 请求标识与客户端 IP；无请求时为 `None` |
| `request_payload` / `response_payload` | 经过序列化及截断保护的输入和输出 |
| `status_code` / `error_message` | 状态码及异常信息 |
| `start_at` / `end_at` | 带时区的 UTC 起止时间 |
| `duration_ms` | 单调时钟计算的耗时，单位毫秒，不包含存储回调耗时 |

**FastAPI 集成：** 需额外安装 FastAPI；无需显式声明 `Request`，装饰器也能获取请求信息。

```python
from fastapi import FastAPI

from agile.utils import recorder

app = FastAPI()


@app.get("/items/{item_id}")
@recorder(
    name="查询商品",
    redacted_headers={"Authorization", "Cookie", "X-API-Key"},
)
async def get_item(item_id: int):
    return {"id": item_id, "name": "Agile"}
```

放入 `app.py` 后，可用 `uvicorn app:app --reload` 启动。路由装饰器必须在 `@recorder` 上方。

**存储与安全边界：**

- 异步业务函数配合同步回调时，回调在线程池执行；异步回调在当前事件循环等待。
- 同步业务函数配合同步回调时，在调用线程执行；异步回调通过新事件循环等待，必要时在线程池执行。
- 同步函数的异步回调不能复用其他事件循环绑定的数据库连接、Task 或 Future。依赖应用异步资源时，应使用异步业务函数和异步回调。
- 函数返回前会等待存储，因此回调会增加调用延迟；回调失败只记录警告，不替换业务返回值或异常。业务方应自行设置存储超时。
- 不采集当前用户，业务方可用上下文变量在回调中补充；数据库连接、表结构、队列生命周期均由业务方管理。
- HTTP 状态依次考虑返回 Response、注入 Response、结果对象 `http_status`、路由配置和 200；异常优先使用其整数 `status_code`，否则记为 500。
- 仅统计被装饰函数，不含 Web 框架后续校验、序列化、后台任务、流式传输；不消费请求体流和流式响应，不替代 HTTP 全生命周期中间件。
- 请求头默认原样记录。脱敏名称匹配不区分大小写，只替换 `request_payload.headers` 中指定值为 `[REDACTED]`；不会自动脱敏请求体、查询参数、函数实参、独立 `request_id` 或返回值。
- 禁止将单个字符串传给 `redacted_headers`，应使用集合或列表。敏感业务可关闭 `record_request` / `record_response`，或在回调中进一步脱敏。

详细行为与更多说明见 [函数调用记录文档](docs/recorder.md)。`RecordCallback` 是回调类型别名，`log_record` 可直接作为标准日志存储回调复用。

### 5.4 单例初始化任务与字符串构建

#### 5.4.1 singleton：共享资源

**场景：** 进程内只创建一次客户端或服务，并提供显式销毁入口。

```python
from agile.utils import singleton


@singleton
class Client:
    def __init__(self, endpoint: str):
        self.endpoint = endpoint
        self.closed = False

    def close(self):
        self.closed = True


first = Client("service-a")
second = Client("service-b")
print(first is second)
print(second.endpoint)
print(Client.monitor_info())
Client.destroy()
third = Client("service-c")
print(third is first)
Client.destroy()
```

输出中的身份判断依次为 `True`、`False`，第二次构造不会重新初始化，地址仍为 `service-a`。

- 构造过程有锁；被装饰类及其子类按具体类分别缓存实例，初始化只执行一次。
- `monitor_info()` 返回类名、创建时间、创建线程及构造调用次数；未创建或销毁后返回空字典。监控数据模型为同模块的 `MonitorData`。
- `destroy()` 优先调用实例 `close()`，否则调用 `dispose()`，然后移除实例及监控缓存；下次构造会重新初始化。
- 仅保证**当前 Python 进程**中的单例；多 worker 各有一份。销毁不消除外部已有引用，仍需业务方管理引用生命周期。

#### 5.4.2 TaskInitializer：初始化任务

**场景：** 启动时预热缓存、加载资源，或先注册任务再统一执行。

```python
from agile.utils.task_initializer import InitTask, TaskInitializer

initializer = TaskInitializer()


def warm_cache():
    print("缓存预热完成")


pending_task = initializer.add_task(warm_cache, lazy=True, desc="缓存预热")
initializer.run()
initializer.run()
initializer.run(reload=True)
print(pending_task.ran_completed)


@initializer.task(desc="立即初始化")
def initialize_metrics():
    print("指标初始化完成")


standalone = InitTask(func=lambda: print("独立任务"), desc="单独执行")
standalone.run()
```

- `add_task(func, lazy=False, desc=None)` 返回 `InitTask`。默认添加后立即触发 `run()`，也可能执行之前尚未运行的延迟任务。
- `run(reload=False)` 跳过已完成任务；`reload=True` 会重新执行所有任务。
- `task` 支持裸装饰器及带参数装饰器，注册时立即执行，且**返回 InitTask 对象而非原函数**；之后可调用该对象的 `run()` 或访问 `func`。
- `InitTask.run()` 自身也会跳过已完成任务；失败时异常向外传播，不会标记完成。
- 任务保存在集合中，按函数身份去重，**不保证执行顺序**；仅用于同步无参函数。不要直接注册异步函数或有严格依赖顺序的任务。
- `TaskInitializer` 本身不是单例；每个实例维护自己的任务集合。

#### 5.4.3 StringBuilder：文本拼装

**场景：** 拼接报告、提示词、多行输出，避免分散管理字符串状态。

```python
from agile.utils.string_utils import StringBuilder

builder = StringBuilder("系统提示：")
builder.append("请根据资料回答。\n").append("资料：Agile 是 Python 工具包。")
print(builder.to_string())
print(builder.length())
print(str(builder))
builder.clear().append("新内容")
print(builder.to_string())
```

继承 `io.StringIO`，支持 `append` 链式追加、`to_string`、`clear`、`length`、`str/repr`。`append` 需要字符串，不会自动将任意对象转成文本。


### 5.5 模型增强枚举与业务异常

#### 5.5.1 BaseModelEnhance：模型访问及校验增强

**场景：** 接收外部表单，将空字符串归一化，并向前端返回可读的字段校验错误。

```python
from pydantic import Field, ValidationError

from agile.utils.pydantic_extension import BaseModelEnhance, FieldErrorConfig


class CreateUser(BaseModelEnhance):
    name: str = Field(min_length=1)
    age: int = Field(ge=18)
    remark: str | None = None

    @classmethod
    def get_empty_str_to_none(cls) -> bool | set[str]:
        return {"remark"}

    @classmethod
    def get_field_errors(cls) -> list[FieldErrorConfig]:
        return [FieldErrorConfig(field_name="age", error_message="年龄必须为不小于 18 的整数")]


user = CreateUser(name="张三", age=20, remark="   ")
print(user["name"])
print(user.get("missing", "默认值"))
print(user.remark)

try:
    CreateUser(name="李四", age=16)
except ValidationError as error:
    print(error.errors()[0]["msg"])
```

- `model_config` 默认 `arbitrary_types_allowed=True`、`extra="allow"`。
- `model["field"]` 和 `get("field", default)` 只访问**模型声明字段**；未知字段的下标访问抛 `KeyError`，即使额外字段被允许，也不能通过该下标接口读取。
- `get_empty_str_to_none()` 默认 `False`；`True` 处理全部字段，字段名集合只处理指定字段。只将空或纯空白字符串转成 `None`，不裁剪正常文本；对应字段仍需允许 `None`，否则继续报校验错误。
- `FieldErrorConfig(field_name=..., error_message=..., func=...)` 使用 Python 字段名，不是 alias；支持匹配别名和字段内部的嵌套错误路径。
- 默认替换错误消息并保留 `ValidationError` 结构；若配置 `func`，它优先执行，接收 Pydantic `ErrorDetails` 字典并返回一个异常对象，该异常将被抛出。

**将字段错误转换为业务异常：** 以下片段接续前面导入，可独立定义请求模型。

```python
from agile.commons import BizError, ErrorCode
from agile.utils.pydantic_extension import BaseModelEnhance, FieldErrorConfig


class RequiredCount(BaseModelEnhance):
    count: int

    @classmethod
    def get_field_errors(cls) -> list[FieldErrorConfig]:
        return [
            FieldErrorConfig(
                field_name="count",
                func=lambda error: BizError(
                    error_code=ErrorCode.PARAM_TYPE_ERROR,
                    message="count 必须为整数",
                    data={"location": error["loc"]},
                ),
            )
        ]


try:
    RequiredCount(count="invalid")
except BizError as error:
    print(error.to_dict())
```

#### 5.5.2 带标签枚举

**场景：** 同时维护机器值和展示名称，生成下拉列表或 LLM 输出格式说明。

```python
from agile.commons import LabeledIntEnum, LabeledStrEnum


class OrderStatus(LabeledStrEnum):
    CREATED = ("created", "待支付")
    PAID = ("paid", "已支付")


class Priority(LabeledIntEnum):
    LOW = (1, "低")
    HIGH = (2, "高")


print(OrderStatus.PAID.value, OrderStatus.PAID.label)
print(OrderStatus.PAID.display())
print(OrderStatus.get_all())
print(OrderStatus.get_format_instructions(title="订单状态可选值："))
print(OrderStatus.from_value("paid"))
print(OrderStatus.from_name("PAID"))
print(Priority.HIGH.value, Priority.HIGH.label)
```

两个枚举共享 `label/display/get_all/get_format_instructions/from_value/from_name`。`from_value` / `from_name` 找不到返回 `None`，匹配不自动忽略大小写；标准枚举构造方式 `OrderStatus("paid")` 仍可使用，但未找到时按标准枚举行为抛异常。

#### 5.5.3 BizError 与 ErrorCode

**场景：** 统一业务失败语义，同时保留模块、上下文和原始异常。

```python
from agile.commons import BizError, ErrorCode

try:
    raise BizError(
        error_code=ErrorCode.RESOURCE_NOT_FOUND,
        message="商品不存在",
        module="catalog",
        data={"product_id": "missing"},
    )
except BizError as error:
    print(error.code)
    print(error.to_dict())
    print(str(error))

custom_error = BizError.from_error_code("BIZ-001", message="自定义业务失败")
custom_error.with_module("checkout").with_data({"order_id": "order-001"})
custom_error.with_message("订单不可结算")
print(custom_error.to_dict())
```

`error_code` 可传 `ErrorCode`、整数、数字字符串、枚举名称或自定义字符串；内部 `code` 统一为字符串。未传或空白时使用 `UNKNOWN_ERROR("99999")`。已知错误码默认消息为枚举标签，未知自定义码建议显式传 `message`。

内置错误码分类：

| 范围 | 场景 | 示例 |
| --- | --- | --- |
| `1xxxx` | 请求及参数 | `BAD_REQUEST`、`VALIDATION_FAILED`、`PARAM_REQUIRED`、`PARAM_TYPE_ERROR`、`PARAM_VALUE_INVALID`、`BODY_PARSE_ERROR`、`URL_NOT_FOUND`、`METHOD_NOT_ALLOWED` |
| `2xxxx` | 登录认证和权限 | `UNAUTHORIZED`、`IDENTITY_INVALID`、`IDENTITY_EXPIRED`、`FORBIDDEN`、`OPERATION_DENIED` |
| `3xxxx` | 数据资源 | `RESOURCE_NOT_FOUND`、`RESOURCE_EXISTS`、`RESOURCE_CONFLICT`、`RESOURCE_LOCKED`、`DATA_STATE_ERROR` |
| `4xxxx` | 业务操作 | `OPERATION_FAILED`、`OPERATION_FREQUENT`、`INVALID_STATUS`、`LIMIT_EXCEEDED` |
| `5xxxx` | 内部服务 | `SERVER_ERROR`、`DATABASE_ERROR`、`CACHE_ERROR`、`TASK_EXECUTION_ERROR`、`DEPENDENCY_ERROR` |
| `6xxxx` | 外部服务 | `THIRD_PARTY_ERROR`、`API_REQUEST_FAILED`、`API_RESPONSE_ERROR` |
| `99999` | 未知 | `UNKNOWN_ERROR` |

可用 `ErrorCode.get_all()` 查看具体值与消息。`cause` 用于保存原始异常；需要 Python 异常链时仍应使用 `raise BizError(..., cause=original) from original`。Agile 不自动安装 Web 全局异常处理器，响应映射由应用完成。

### 5.6 Web 响应与分页

#### 5.6.1 R：统一响应结构

**场景：** 为 Web 接口统一成功/失败结构、业务码、HTTP 状态和追踪 ID。模型本身不依赖 FastAPI。

```python
from datetime import datetime
from http import HTTPStatus

from agile.web import R

success = R[dict].success(
    data={"id": 1, "created_at": datetime(2026, 11, 12, 10, 30)},
    message="查询成功",
).set_track_id("trace-001")

failure = R.error(
    code=30001,
    message="资源不存在",
    http_status=HTTPStatus.NOT_FOUND,
)

print(success.model_dump_json())
print(failure.model_dump_json())
print(R.extract_data(success, default_value={}))
```

响应字段：`code/message/data/http_status/succeed/track_id`。`datetime_format` 为序列化配置字段，不包含在输出中。

| 接口 | 说明 |
| --- | --- |
| `R.success(...)` | 默认 `code=200`、`message="OK"`、`http_status=200`、`succeed=True` |
| `R.error(...)` | 默认 `code=500`、`message="Internal Server Error"`、`http_status=500`、`succeed=False` |
| `R.build(is_success=..., datetime_format=None)` | 基础构建入口 |
| `set_code/set_message/set_data/set_track_id` | 链式设置，不会自动根据业务码推导成功状态 |
| `set_http_status(status, response=None)` | 设置模型状态；传入可写 `status_code` 的 Response 时同步修改实际 HTTP 状态 |
| `R.extract_data(result, default_value)` | 成功且数据不是 `None` 时返回数据，否则返回默认值 |

默认 datetime 格式为 `%Y-%m-%d %H:%M:%S`，可传 `datetime_format` 覆盖；对带时区 datetime 会先转为运行环境的本地时区。日期数据会递归处理字典、集合及 Pydantic 模型。

**必须注意：**

- 请通过 `success/error/build` 工厂构造；当前 `R.__init__` 会重置业务字段，不要使用 `R(code=..., data=...)` 作为构造入口。
- 当前 `data` 序列化器将假值 `0/False/""/[]/{}` 输出为 `null`；必须保留这些值时可包装为非空对象，例如 `{"items": []}`。
- `http_status` 字段不会自动改变实际 Web 响应状态；框架集成时要传入 Response 或构建显式状态码的响应对象。
- `R.code` 是整数，而 `BizError.code` 是字符串；自定义非数字错误码应自行约定转换方式，不能直接强制转换。

**FastAPI 显式状态码示例：**

```python
from http import HTTPStatus

from fastapi import FastAPI, Response

from agile.web import R

app = FastAPI()


@app.get("/missing")
def missing(response: Response):
    return R.error(code=30001, message="资源不存在").set_http_status(
        HTTPStatus.NOT_FOUND, response=response
    )
```

`StatusWritableResponse` 是可写 `status_code` 的协议，无需业务 Response 继承它。

#### 5.6.2 动态响应模型

**场景：** 为接口生成有特定数据类型和字段描述的 Pydantic 模型。

```python
from pydantic import BaseModel

from agile.web.common_result import gen_response_model


class UserView(BaseModel):
    id: int
    name: str


UserResponse = gen_response_model(
    "UserResponse",
    data_type=UserView,
    data_desc="用户信息",
    code_default=200,
)
print(UserResponse(data=UserView(id=1, name="张三")).model_dump_json())
```

`gen_response_model` 支持覆盖 `code/message/succeed/http_status` 的默认值与描述。它生成的是独立 Pydantic 模型，**不是 R 子类**，无链式接口或 `track_id`；其默认业务码是 **0**，与 `R.success()` 的 200 不同，建议显式统一。

#### 5.6.3 分页请求与响应

**场景：** 将页码转换为数据库偏移量，返回总页数及翻页信息。

```python
from agile.web import PagingRequest, PagingResponse, R

request = PagingRequest(current=2, size=10)
print(request.get_offset())

page = PagingResponse(
    records=[{"id": 11}, {"id": 12}],
    total=23,
    current=request.current,
    size=request.size,
    extension={"keyword": "Agile"},
)
print(page.pages, page.has_previous(), page.has_next())
print(R.success(data=page).model_dump_json())

request.unlimited()
print(request.current, request.size)
```

偏移量为 10，总页数为 3。`PagingRequest` 默认 `current=1/size=10`；`unlimited()` 将页码设为 1、页大小设为 `sys.maxsize`，并不替你执行无限量数据库查询。

`PagingResponse` 默认 `current=0`，业务应显式设置；`pages` 是会参与序列化的计算字段，`size=0` 时为 0。当前分页模型没有正数约束，外部请求应自行限制 `current>=1` 和合理的 `size`，避免负偏移或超大查询。

### 5.7 中英文时间提取

**场景：** 从“查询昨天的订单”“明天下午三点提醒我”等输入中提取时间点或范围，为搜索和过滤提供条件。

```python
from datetime import datetime

from agile.utils.extract_time_range import TimeRangeExtractor, extract_time_range

base_time = datetime(2026, 11, 12, 10, 0, 0)
print(extract_time_range("查询昨天的订单", now=base_time))
print(extract_time_range("明天下午3点开会", now=base_time))
print(extract_time_range("yesterday", now=base_time, language="en"))

extractor = TimeRangeExtractor(language="zh")
print(extractor.extract("2026年11月", now=base_time))
print(extractor.extract_all("明天下午3点开会", now=base_time))
```

“昨天”在固定基准下返回 `["2026-11-11 00:00:00", "2026-11-11 23:59:59"]`；“明天下午3点”返回 `["2026-11-13 15:00:00"]`。

- `extract_time_range(text, now=None, language="zh")`：便捷函数。
- `TimeRangeExtractor(language="zh").extract(text, now=None)`：复用解析器；`zh` 为中文，英文请显式传 `en`。
- `extract_all(...)`：返回各个原始匹配，包括 `matched_text/pattern_name/slot_type/start_pos/end_pos/time_range`；它不是多个完整业务事件的分组器。
- 返回列表可能为 `[]`、单元素时间点或两个元素的起止范围；空文本或无匹配时为 `[]`。时间通常为 `YYYY-MM-DD HH:MM:SS`，不含时区信息；当前部分纯时段范围的起点只有分钟精度，业务侧应先统一格式。
- 支持的规则包括日期、时间、上午/下午等时段、相对日期、星期、月/年/季度、前后偏移及近期范围；这是正则与槽位组合解析，不是通用自然语言模型。
- 未传 `now` 时使用系统当前时间；测试和业务回放建议固定基准。不要把返回字符串当作 UTC，时区需业务自行约定。

**当前精度限制：** 仅有年/月而没有日的绝对日期，可能以基准时间的日补全，并不一定展开为整年/整月。上例 `2026年11月` 在指定基准下实际返回 2026-11-12 当天范围，而不是整个 11 月；需要按自然月查询时，应由业务方明确计算月初和月末。

**扩展入口：** 同模块提供 `Language`、`SlotType`、`OffsetType`、`TimeSlot`、`ParseResult`、`SlotParserBase`、`ChineseSlotParser`、`EnglishSlotParser`、`TimeSlotCombiner`。可以通过 `extractor.parser.parse(text)` 检查槽位；`TimeSlot` 提供 `has_date/has_time/has_offset/merge_with`，组合器的 `combine(slots, now)` 负责生成时间范围。复杂多事件、歧义日期和非法日期应在业务层增加校验，不要假设所有表达式都能正确解析。

### 5.8 BM25 全文检索

**场景：** 本地中文知识库、关键词召回、无需 Embedding 服务的全文搜索。

```python
from pathlib import Path
from tempfile import TemporaryDirectory

from agile.search import BM25Searcher

with TemporaryDirectory() as temporary_dir:
    index_dir = Path(temporary_dir) / "knowledge-index"
    searcher = BM25Searcher(index_dir=str(index_dir))
    documents = [
        {"id": "doc-1", "content": "Agile 支持本地缓存和日志管理"},
        {"id": "doc-2", "content": "Milvus 用于向量相似度检索"},
        {"id": "doc-3", "content": "使用缓存减少重复查询"},
    ]
    print(searcher.search("缓存", top_k=3, docs=documents))
    print(searcher.search("向量检索", top_k=3))
```

| 参数或接口 | 说明 |
| --- | --- |
| `BM25Searcher(index_dir=None, id_field="id", content_field="content", analyzer=None)` | 配置索引目录、主键字段、正文字段和 Whoosh 分析器 |
| `search(query, top_k=20, group=OrGroup, docs=None)` | 可先增量写入文档再搜索，返回按相关性排序的**字符串主键列表** |
| `get_or_create_index()` | 创建或打开 Whoosh 索引，供需要底层操作的调用方使用 |

- 默认使用 `JiebaAnalyzer` / `JiebaTokenizer` 进行中文分词；自定义分析器可从 `agile.search.bm25_searcher` 导入相关类，或传入其他 Whoosh `Analyzer`。
- 多词默认按 OR 组合；需要全部词匹配时传 `group=whoosh.qparser.AndGroup`。
- `docs` 中必须包含配置的主键和正文字段。主键转为字符串；同 ID 使用 `update_document` 更新，**不是清空后重建**，也不保存额外业务字段。
- 不传 `docs` 时搜索已有索引；若要持久化，请使用固定目录，下一次创建实例可打开已有索引。
- 默认目录是系统临时目录下的 `bm25_index`，可能被多个实例共用；不同知识库应显式使用独立目录。
- 创建索引目录使用单层 `mkdir`，上级目录需预先存在；并发写入仍受 Whoosh 写锁约束。
- 当前封装不直接返回全文、分数或删除文档接口；可按返回 ID 回查业务数据，或使用底层 Whoosh 索引自行扩展。


### 5.9 向量模型与 Milvus

#### 5.9.1 BaseEmbedModel：接入向量服务

**场景：** 将不同模型供应商统一为异步向量接口，供 Milvus 写入及查询复用。

需实现 `__init__`、`async embed(text, model=None, dim=None)` 和 `async embed_batch(texts, model=None, dim=None)`。子类构造时调用父类构造，保存 `dim/max_token/encoding_name/encoding`。

下面是**只验证接口流程的确定性假向量模型，不具备语义检索能力**。实际知识库请替换为真实 Embedding 服务，且保证写入与查询使用同一模型和维度。

```python
import asyncio
from hashlib import sha256

from agile.db.vector import BaseEmbedModel


class DemoEmbedding(BaseEmbedModel):
    def __init__(self, dim: int = 4, **data):
        super().__init__(dim=dim, **data)

    async def embed(self, text: str, model: str = None, dim: int = None) -> list[float]:
        target_dim = dim if dim is not None else self.dim
        digest = sha256(text.encode("utf-8")).digest()
        return [digest[index % len(digest)] / 255.0 for index in range(target_dim)]

    async def embed_batch(
        self, texts: list[str], model: str = None, dim: int = None
    ) -> list[list[float]]:
        return [await self.embed(text, model=model, dim=dim) for text in texts]


embedding = DemoEmbedding(dim=4)
print(asyncio.run(embedding.embed("Agile")))
print(BaseEmbedModel.similarity([1.0, 0.0], [1.0, 0.0]))
token_ids, token_count = embedding.get_tokens("Agile 使用手册")
print(token_count)
```

- `similarity(vec1, vec2, eps=1e-12)` 计算余弦相似度，结果限制在 `[-1, 1]`；零向量返回 0，形状不一致抛 `ValueError`。
- `get_tokens(text)` 返回 `(token_ids, token_count)`，默认使用 tiktoken 的 `cl100k_base`；首次加载编码可能需要下载并缓存资源。
- `max_token` 默认 8192，目前只是属性，**不自动检查、截断或分块**；应按实际 Embedding 服务限制在业务侧实现。

#### 5.9.2 连接、初始化、写入与搜索

**场景：** 将知识片段保存为向量，按相似度召回，并保留来源信息。

以下片段接续上一节的 `DemoEmbedding` 定义。运行前设置 `MILVUS_URI` 和 `MILVUS_TOKEN`，指向测试环境；示例会创建集合并写入数据，但不会删除集合。

```python
import asyncio
import os

from langchain_core.documents import Document

from agile.db.vector import MilvusManager


async def milvus_demo():
    async with MilvusManager(
        uri=os.environ["MILVUS_URI"],
        token=os.environ["MILVUS_TOKEN"],
        embedding_model=DemoEmbedding(dim=4),
        default_collection_name="agile_manual_demo",
        vector_dim=4,
        params_nlist=1,
        params_nprobe=1,
    ) as manager:
        await manager.ensure_collection_ready()
        await manager.insert([
            Document(
                id="manual-001",
                page_content="Agile 支持内存缓存",
                metadata={"source": "manual", "category": "cache"},
            ),
            Document(
                id="manual-002",
                page_content="Milvus 提供向量检索",
                metadata={"source": "manual", "category": "search"},
            ),
        ])
        results = await manager.search("Agile 支持内存缓存", top_k=2)
        for hits in results:
            for hit in hits:
                print(hit.id, hit.distance, hit.entity.get("text"))
        print(await manager.get_by_ids(["manual-001"]))
        print(await manager.get_collection_count())
        print(await manager.get_collection_stats())


asyncio.run(milvus_demo())
```

`params_nlist=1/params_nprobe=1` 只是为了少量演示数据；生产索引参数需按数据量及延迟目标调整。`insert` 是插入而非 upsert，不保证重复 ID 覆盖，反复运行示例前应管理已有测试数据。

**必要顺序：** 创建 Manager → `ensure_collection_ready` → 写入/查询 → `close`。即使服务端集合已存在，新 Manager 也需要初始化，以填充本地已初始化集合缓存；`get_collection` 不会自动发现所有现有集合。

| 构造参数 | 默认值 / 说明 |
| --- | --- |
| `uri/token/embedding_model` | 必填；URI、令牌不得为空 |
| `default_collection_name` | 可省略，但操作时必须提供集合名 |
| `default_primary_field/default_text_field/default_vector_field` | `id/text/vector`；默认元数据字段为 `metadata` |
| `vector_dim` | 1536，必须为正且与模型输出一致 |
| `index_type` | `MilvusIndexType.IVF_FLAT`；构造时传枚举，不要传字符串 |
| `metric_type` | `"L2"`；创建索引和查询需保持一致 |
| `params_nlist/params_nprobe` | `128/10`；`nprobe` 不能大于 `nlist` |
| `search_timeout` | 30 秒，必须为正 |
| `allow_dynamic_field` | `False`；控制创建集合时是否允许动态字段 |
| `default_field_schemas` | 默认 `id: VARCHAR`、`text: VARCHAR`、`vector: FLOAT_VECTOR`、`metadata: JSON` |
| `default_index_specs` | 为默认向量索引追加额外索引规格 |
| `collection_config` | `{集合名: 字段映射配置}`，用于多集合字段映射 |

#### 5.9.3 API 速查

除特别标明外，下表方法都需要 `await`：

| 方法 | 作用及返回 |
| --- | --- |
| `ensure_collection_ready(collection_name=None, field_schemas=None, index_specs=None, collection_config=None, allow_dynamic_field=None)` | 确保集合存在并加载；建议启动时调用 |
| `create_collection(collection_name=None, collection_desc=None, field_schemas=None, index_specs=None, collection_config=None)` | 创建集合；描述、schema 等为关键字参数；已存在则警告并返回 |
| `get_collection(collection_name)` | 返回已初始化的 ORM `Collection`，否则 `None` |
| `insert(documents, collection_name=None)` | 插入 `Document` 或字典列表，完成后 flush，无 ID 列表返回 |
| `search(query, *, collection_name=None, filter_expr=None, output_fields=None, search_params=None, top_k=5, timeout=None)` | 返回原始 Milvus 搜索结果，不是 `Document` 列表 |
| `get_by_ids(ids, collection_name=None, output_fields=None)` | 按主键取 `Document` 列表，异常时记录日志并返回 `[]` |
| `delete_by_ids(ids, collection_name=None)` | 按主键删除并 flush |
| `get_collection_count(collection_name=None)` | 获取记录数 |
| `get_collection_stats(collection_name=None)` | 返回名称、数量、分片、schema 和索引统计 |
| `list_collections()` | 列出服务端集合 |
| `clear_collection(collection_name)` | 删除数据，保留结构；谨慎执行 |
| `delete_collection(collection_name)` | 删除整个集合并清理本地缓存；不可逆操作 |
| `add_collection_config(collection_name, collection_config)` | **同步**注册字段映射；初始化后不能修改 |
| `trans_to_documents(results, collection_name=None)` | **同步**转换结果，当前实体结构存在限制，见下文 |
| `health_check()` | **同步**探测连接，返回布尔值 |
| `close()` | **同步**断开默认连接并清理本地集合缓存 |

`async with` 会在退出时调用 `close`。虽然多数方法声明为异步，部分内部 ORM 操作仍是同步调用，不能认为所有访问均不阻塞事件循环。

#### 5.9.4 字典插入与过滤

接续一个已完成初始化的 `manager`，在异步函数内执行：

```python
async def insert_and_filter(manager):
    await manager.insert([
        {
            "id": "faq-001",
            "text": "如何设置缓存 TTL？",
            "metadata": {"category": "faq"},
        }
    ])
    return await manager.search(
        "缓存过期时间",
        filter_expr='metadata["category"] == "faq"',
        output_fields=["id", "text", "metadata"],
        top_k=5,
    )
```

`Document` 会批量调用 `embed_batch`；没有 ID 时生成 UUID，生成值不会写回原对象或作为返回值返回，需后续精确管理时应自行指定 ID。字典必须匹配 schema 并自行提供主键；默认补 `metadata={}`，按映射文本生成向量。即使字典已带向量，当前实现仍会调用 `embed`，只是不会覆盖已提供的向量。

`allow_dynamic_field=False` 时，多余字典字段会被拒绝；额外业务字段应定义到 schema，或放入 `metadata`。启用动态字段只是创建 schema 的选项，不会自动迁移已有集合。过滤表达式遵循 Milvus 语法，勿直接拼接不可信文本；当前 ID 查询/删除也采用字符串表达式，应限制 ID 格式，特别避免直接使用含引号的外部输入。

#### 5.9.5 自定义 schema、索引和多集合映射

**场景：** 不同知识库使用不同字段名，或为业务分类增加标量索引。下例在异步上下文中接收现有 Manager：

```python
from pymilvus import DataType, FieldSchema

from agile.db.vector import MilvusIndexSpec, MilvusIndexType
from agile.db.vector.milvus.milvus_manager import MilvusCollectionConfig


async def prepare_faq_collection(manager):
    await manager.ensure_collection_ready(
        collection_name="faq_custom",
        field_schemas=[
            FieldSchema(name="doc_id", dtype=DataType.VARCHAR, is_primary=True, max_length=128),
            FieldSchema(name="question", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=manager.vector_dim),
            FieldSchema(name="metadata", dtype=DataType.JSON),
            FieldSchema(name="category", dtype=DataType.VARCHAR, max_length=64),
        ],
        collection_config=MilvusCollectionConfig(
            primary_field="doc_id",
            text_field="question",
            vector_field="embedding",
        ),
        index_specs=[
            MilvusIndexSpec(field_name="category", index_type=MilvusIndexType.INVERTED)
        ],
        allow_dynamic_field=False,
    )
    await manager.insert(
        [{"doc_id": "faq-101", "question": "如何配置日志？", "category": "logging"}],
        collection_name="faq_custom",
    )
```

字段映射也可用字典，键为 `primary_field/text_field/vector_field/metadata_field`，四个字段名必须非空且不重复。也可在构造参数 `collection_config` 中批量注册，或初始化前调用 `add_collection_config`。**只改映射不会自动重命名默认 schema**，应像示例一样显式传入匹配的 `field_schemas`。

`MilvusIndexSpec(field_name, index_type, index_params=None, index_name=None)` 及等价字典用于描述索引；`index_params` 是透传给创建索引的参数字典。管理器会先创建默认向量索引，再创建附加索引，同一个字段不能重复定义。非默认向量字段的索引需要显式提供参数。

枚举包含标量 `STL_RAW/INVERTED`，以及向量 `FLAT/IVF_FLAT/IVF_SQ8/IVF_PQ/HNSW/RHNSW_FLAT/RHNSW_SQ/RHNSW_PQ/ANNOY/DISKANN`；提供 `normalize_index_type/is_valid_index_type/is_vector_index/is_scalar_index` 辅助方法。**枚举存在不代表连接的 Milvus 版本支持该索引**，实际可用性由服务端决定，不宜直接照搬源码中的容量建议。

#### 5.9.6 当前兼容性与限制

- `search` 捕获搜索异常并返回 `[]`，空结果可能代表“无匹配”或“执行失败”；应结合日志、监控及 `health_check` 判断。
- `trans_to_documents` 目前从 `hit.entity.get("entity")` 读取正文数据；若实际结果字段直接位于 `hit.entity`，会得到空正文。使用前需验证实体结构；上面的示例直接读取原始 Hit，避免依赖该假设。
- `MilvusRetriever` 声明了 `milvus_manager/collection_name/top_k/reranker`，预期用于 LangChain 的 `invoke/ainvoke`，但内部调用的是当前 Manager **不存在的 `sync_search/async_search`**，且假设结果已经是 `Document`。因此暂不能直接作为可运行检索链；请使用 `await manager.search(...)`，自行按实际 Hit 结构转换，或先完成业务适配。
- 检索器的可选 `reranker` 预期提供同步 `compress_documents(documents=..., query=...)`，异步路径也没有自动异步化该操作。
- 字段映射已覆盖主要读写路径，但部分 schema 补全和字典插入逻辑仍硬编码 `metadata`；当前建议保留此元数据字段名。
- 索引规格归一化目前未保留自定义 `index_name`，不要依赖指定索引名生效；自定义 schema 也不会自动迁移已有集合。
- `clear_collection` 当前以“主键不等于空字符串”删除数据，适用于默认字符串主键，不应视为任意主键类型的通用 truncate。
- Manager 使用共享的 `default` 连接别名，关闭一个实例可能影响其他使用此别名的组件；应用应统一管理连接生命周期。


### 5.10 Agent 结构化工具

#### 5.10.1 自动注册业务工具

**场景：** 把业务类的方法转为 LangChain `StructuredTool`，统一生成工具名称、描述和参数 schema。

```python
from pydantic import BaseModel, Field

from agile.agent.tools.base_structured_tools import BaseStructuredTools
from agile.agent.tools.tool_decorators import structured_tool
from agile.agent.tools.tool_response import ToolCommonResponse


class AddInput(BaseModel):
    left: int = Field(description="左操作数")
    right: int = Field(description="右操作数")


class MathTools(BaseStructuredTools):
    @structured_tool(name="add", description="计算两个整数之和", args_schema=AddInput)
    def add_numbers(self, left: int, right: int) -> ToolCommonResponse:
        return ToolCommonResponse(data={"result": left + right})


math_tools = MathTools()
print([tool.name for tool in math_tools.get_tools()])
result = math_tools.add.invoke({"left": 2, "right": 3})
print(result.model_dump())
```

`BaseStructuredTools.__init__` 自动发现类及继承来的标记方法，注册并通过工具名挂到实例上；上例原方法叫 `add_numbers`，工具属性叫 `add`。若工具方法依赖实例状态，子类应先初始化状态，再调用 `super().__init__()`。

| 接口 | 含义 |
| --- | --- |
| `@structured_tool` / `@structured_tool(...)` | 标记工具方法；可传 `name/description/args_schema/depends_on` |
| `discover_tools()` | 返回 `ToolSpec` 列表，包含 `name/method/description/args_schema` |
| `register_tools()` | 发现并注册工具，返回列表；通常构造时自动执行一次 |
| `get_tools()` | 返回已注册工具列表的副本，可交给业务方的 LangChain Agent |
| `CompatibleStructuredTool` | `StructuredTool` 子类，额外提供与名称一致的 `__name__` 属性 |
| `ToolCommonResponse` | 统一工具结果：`data/message/succeed/metadata` |

`args_schema` 可为 Pydantic 模型或 JSON schema 字典。未显式传描述时，应给方法写 docstring，供 LangChain 使用。调用注册后的工具应使用 `.invoke({...})`，不是把工具属性当普通方法调用。

`ToolCommonResponse.data` 仅支持列表、字典或 `None`，标量请包装为 `{"result": value}`；`succeed` 默认 `True`，未传消息时按成功/失败填入 `Execution successful` / `Execution failed`。

**当前限制：**

- `depends_on` 目前只存储装饰器元数据，注册器不做依赖校验、排序、注入或执行编排。
- 自动注册按同步 `func=` 构造工具，不会为 `async def` 自动设置 `coroutine=`；本文自动注册示例仅使用同步方法。
- 注册时会按工具名替换实例属性；工具名应唯一，并避免与业务属性和 `get_tools/register_tools` 等方法冲突。
- 原方法与工具同名时，重复注册可能受到已替换实例属性影响，建议按构造时的一次注册使用，不依赖任意次数重注册。
- 这里只负责工具注册，不会创建模型、Agent、执行器或自动授权工具调用。

#### 5.10.2 通用执行工具

**场景：** 给受控的业务流程提供 HTTP 请求或简单命令执行能力。导入所在模块需要 `requests`。

```python
from agile.agent.tools.impl.comm_executive_capacity_tools import CommExecutiveCapacityTools

tools = CommExecutiveCapacityTools()
print([tool.name for tool in tools.get_tools()])
command_result = tools.run_command.invoke({"command": "python --version", "timeout": 5})
print(command_result.model_dump())
```

**HTTP 工具 `fetch_url`：**

```python
from agile.agent.tools.impl.comm_executive_capacity_tools import CommExecutiveCapacityTools


def request_healthcheck(allowed_health_url: str):
    tools = CommExecutiveCapacityTools()
    return tools.fetch_url.invoke({
        "url": allowed_health_url,
        "method": "GET",
        "params": {"verbose": "true"},
        "timeout": 5,
        "verify": True,
    })
```

此片段只定义函数，不自动访问网络；`allowed_health_url` 应由业务方校验后传入。

| 工具 | 参数与结果 |
| --- | --- |
| `fetch_url(url, method="GET", headers=None, params=None, data=None, timeout=10, verify=True)` | 支持常见 HTTP 方法，`data` 作为请求体/表单参数；返回 `status_code/text/content/json/headers` |
| `run_command(command, timeout=10)` | `shlex.split` 分词后使用 `subprocess.run`，返回 `stdout/stderr/exit_code`；超时和失败通过 `ToolCommonResponse` 表达 |

`fetch_url` 对 HTTP 状态调用 `raise_for_status`，失败返回 `succeed=False`。JSON 响应按 Content-Type 判断后解析；二进制 `content` 仍是 bytes，不是直接可 JSON 序列化的业务数据。注意函数实际默认 `verify=True`，不要被旧 docstring 的相反描述误导。

**安全边界：** `run_command` 拒绝部分管道、重定向等字符，且不启用 shell，但**不是沙箱或完备的命令授权系统**，仍能启动具有文件修改、网络访问等权限的程序。`fetch_url` 也不提供 SSRF 防护或域名白名单。接入外部用户或模型前，应由业务方限制命令、参数、URL、网络出口和运行权限，使用隔离环境；不要向不可信 Agent 无限制开放。

Windows 的 `dir` 等 shell 内建命令不能作为普通可执行文件直接运行，且 `shlex` 使用 POSIX 风格分词；复杂 Windows 路径和引号应单独验证。

### 5.11 命令行能力

#### 5.11.1 内置 agile 命令

**场景：** 查看包的 CLI 入口及 Typer 命令示例。当前只实现问候功能，不是完整的项目管理命令行。由于只注册了一个命令，Typer 将该命令提升为根命令，实际用法不带 `greet` 子命令名。

```bash
agile --help
agile --name 张三
agile -n 张三 --formal
```

`--name/-n` 为姓名，未传时会交互询问；`--formal/-f` 切换正式问候。开发环境也可使用：

```bash
python -m agile.agile_shell --name 张三
```

源码内的帮助文案仍展示 `agile greet ...`，但当前会报 `Got unexpected extra argument (greet)`，请以上述实际入口用法为准。

#### 5.11.2 Argparser：自定义脚本参数

**场景：** 为业务脚本封装一组参数定义，并取得解析值及元数据。

```python
from agile.utils.argparser import Argument, Argparser

parser = Argparser(desc="离线数据导入")
parser.add_args([
    Argument(arg_name="path", arg_type=str, required=True, help="输入文件"),
    Argument(arg_name="limit", arg_type=int, required=False, default_val=100),
])
arguments = parser.list_args(argv=["--path", "data.json", "--limit", "20"])
for argument in arguments:
    print(argument.arg_name_with_prefix, argument.current_val)

print(parser.get_arg("--path", argv=["--path", "data.json"]).current_val)
```

`Argument` 字段包括 `arg_prefix="--"`、`arg_name`、`arg_type=str`、`required=True`、`default_val`、`current_val`、`help`。可通过 `add_arg` 添加一个，或 `add_args` 批量添加。

- `parse(argv=None)` 返回标准 `argparse.Namespace`；`argv=None` 时读取当前进程命令行。
- `list_args(argv=None)` 解析并写入每个定义的 `current_val`，返回 `Argument` 列表。
- `get_arg("--name", argv=None)` 同样会重新解析整组参数，再查找带前缀的名称；找不到返回 `None`。
- `default_val` 只在 `list_args/get_arg` 中补值，未透传给底层 `parse`；仅调用 `parse` 时缺失可选项仍可能为 `None`。
- 当前补值逻辑使用 `param_value or default_val`，显式传入 `0`、`False`、空字符串可能被默认值替换；涉及这些语义时应使用原生 argparse 自行定义。
- 布尔开关不要直接使用 `arg_type=bool` 期待识别 `"false"`；当前封装未暴露 `store_true` 等 action，可改用标准 argparse。

## 6. 综合案例

### 6.1 FastAPI：配置、缓存、审计、分页、业务异常

**场景：** 实现一个可运行的分页商品接口。将下面代码放入业务项目 `app.py`，安装 Agile、`pydantic-settings`、`fastapi` 和 `uvicorn`。

```python
from http import HTTPStatus

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse

from agile.cache import MemoryCache
from agile.commons import BizError, ErrorCode
from agile.utils import recorder
from agile.utils.app_settings import AppSettings
from agile.web import PagingRequest, PagingResponse, R


class Settings(AppSettings):
    cache_ttl: int = 60

    @classmethod
    def get_env_prefix(cls) -> str:
        return "SHOP_"

    @classmethod
    def get_env_file_list(cls) -> list[str]:
        return [".env"]


settings = Settings()
app = FastAPI(title="Agile 示例服务")
cache = MemoryCache[str, list](maxsize=100, default_ttl=settings.cache_ttl)
products = [{"id": index, "name": f"商品 {index}"} for index in range(1, 26)]


@app.exception_handler(BizError)
async def handle_business_error(request: Request, error: BizError):
    status = HTTPStatus.NOT_FOUND if error.error_code == ErrorCode.RESOURCE_NOT_FOUND else HTTPStatus.BAD_REQUEST
    code = int(error.code) if error.code.isdigit() else 40001
    result = R.error(code=code, message=error.message, data=error.data, http_status=status)
    return JSONResponse(status_code=status.value, content=result.model_dump(mode="json"))


@app.get("/products")
@recorder(name="分页商品查询", record_request=False, record_response=False)
def list_products(current: int = Query(1, ge=1), size: int = Query(10, ge=1, le=100)):
    request = PagingRequest(current=current, size=size)
    records = cache.get_or_set("all-products", lambda: list(products))
    offset = request.get_offset()
    page = PagingResponse(
        records=records[offset:offset + size],
        total=len(records),
        current=current,
        size=size,
    )
    return R.success(data=page)


@app.get("/products/{product_id}")
@recorder(name="查询单个商品", record_request=False, record_response=False)
def get_product(product_id: int):
    product = next((item for item in products if item["id"] == product_id), None)
    if product is None:
        raise BizError(error_code=ErrorCode.RESOURCE_NOT_FOUND, message="商品不存在")
    return R.success(data=product)
```

启动和访问：

```bash
uvicorn app:app --reload
```

访问 `/products?current=2&size=10` 返回分页结果；`/products/999` 返回 HTTP 404 及业务错误码 30001。可通过 `SHOP_CACHE_TTL` 调整缓存秒数。示例只读，不涉及修改后缓存失效；多 worker 下每个进程各有缓存。

`recorder` 对普通 `BizError` 会记录 500，因为该异常本身没有 `status_code`；随后全局异常处理器才将它映射为 HTTP 404/400。这再次说明记录的是函数层状态，而非最终 HTTP 响应。若审计要求最终状态，请在业务方定义状态映射或使用 HTTP 中间件。

### 6.2 RAG：关键词召回与向量召回组合

建议按以下职责组合，而不是假设 Agile 已提供完整 RAG 流程：

1. 清洗和分块：由业务负责，保留统一文档 ID。
2. BM25：使用 `BM25Searcher.search(query, docs=...)` 建本地关键词索引，取得主键候选。
3. 向量化：实现真实 `BaseEmbedModel`，将片段写入 Milvus。
4. 向量召回：使用 `await manager.search(query, ...)`，按原始 Hit 提取 ID、正文、距离。
5. 融合与重排：按文档 ID 去重，用业务策略或 RRF 融合，必要时调用自有 reranker。
6. 生成答案：将召回上下文交给业务使用的 LLM，同时使用 `recorder` 记录调用、`timing` 排查延迟。

Agile 目前没有内置融合排序、切分器、LLM 调用器、重排模型或完整问答链；`MilvusRetriever` 的当前适配限制见第 5.9 节。

## 7. 开发测试与常见问题

### 7.1 测试

安装源码、`pytest` 和 `pydantic-settings` 后，在仓库根目录运行离线测试：

```bash
python -m pytest tests --ignore=tests/test_milvus_manager.py
```

需要验证 Web 集成测试时还需安装 `fastapi`、`httpx`；未安装时，部分集成用例可能跳过。计时、环境变量、缓存、单例、枚举、异常、响应、模型增强和 recorder 等都有测试，文件名可作为模块导航。

**不要未经确认直接跑完整测试到生产 Milvus。** 当前 `tests/test_milvus_manager.py` 包含连接 `localhost:19530` 并创建/写入集合的集成演示，而且个别字段有意不满足动态字段配置，不应当作无外部依赖的离线测试。请先配置隔离测试实例并检查测试内容。

### 7.2 常见问题

| 问题 | 处理方式 |
| --- | --- |
| 导入 `AppSettings` 报 `No module named pydantic_settings` | 补装 `pydantic-settings`，当前未列入项目直接依赖 |
| 修改 `.env` 后实例不更新 | `AppSettings` 是实例化时读取，重新创建实例；`EnvHelper.set` 仅写进程，不写文件 |
| 为什么没有加载基础 `.env` | `EnvHelper` 找到环境专属文件就停止，不做合并；`AppSettings` 则是多文件读取 |
| 日志没有输出或出现重复 | 检查 logger 级别、handler、propagate、全局配置；内置错误和普通文件指向同一路径 |
| 缓存为什么在其他 worker 不可见 | `MemoryCache` 是进程内缓存；需要共享时自行实现 `BaseCache` 后端 |
| 缓存过期时间不符合预期 | 检查 TTL 单位、正数限制、默认 TTL 对单项 TTL 的上限影响 |
| `R` 响应里业务码和 HTTP 状态不同 | 两者独立；通过 Response 或显式响应对象设置实际状态 |
| `R.success(data=[])` 输出 `null` | 当前假值序列化限制；包装为 `{"items": []}` |
| recorder 回调报跨事件循环错误 | 同步业务使用同步回调；依赖应用异步资源时使用异步业务与异步回调 |
| recorder 泄露令牌 | 显式配置 `redacted_headers`；请求体及返回值另行脱敏或关闭记录 |
| Milvus 搜索总返回空 | 先初始化集合，检查向量维度、连接、过滤和日志；空列表也可能表示搜索失败 |
| `MilvusRetriever.invoke/ainvoke` 报方法不存在 | 当前接口未对齐，改用 `manager.search` 并自行适配 |
| `structured_tool(depends_on=...)` 没有效果 | 参数只保留元数据，没有依赖编排实现 |
| 工具无法直接当普通函数调用 | 注册后是 `StructuredTool`，请使用 `invoke` |
| 时间解析有偏差 | 固定 `now`、确认语言，检查 `extract_all` 原始匹配；复杂文本需业务校验 |

## 8. 源码导航与许可证

| 路径 | 内容 |
| --- | --- |
| `src/agile/utils/` | 配置、日志、计时、记录器、单例、任务、模型、字符串、时间解析及参数解析 |
| `src/agile/cache/` | 缓存抽象与内存实现 |
| `src/agile/commons/` | 标签枚举、业务错误码及异常 |
| `src/agile/web/` | 通用响应和分页模型 |
| `src/agile/search/` | Whoosh + Jieba 全文搜索 |
| `src/agile/db/vector/` | Embedding 抽象、Milvus Manager 和 Retriever |
| `src/agile/agent/tools/` | 工具装饰器、注册器、统一结果和通用执行工具 |
| `src/agile/config/agile-logger.yaml` | 默认日志配置 |
| `src/agile/agile_shell.py` | Typer 命令行入口 |
| `tests/` | 单元测试与集成演示 |
| `docs/recorder.md` | 调用记录装饰器专项文档 |
| `VERSIONS.md` | 历史变更记录，未完整覆盖当前全部版本 |

项目采用 **MIT License**，详见 [LICENSE](LICENSE)。
