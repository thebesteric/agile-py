import asyncio
import uuid
from dataclasses import dataclass
from enum import Enum, unique
from typing import List, Set, Any, cast, Union

from langchain_core.documents import Document
from pymilvus import MilvusClient, DataType, CollectionSchema, FieldSchema, Collection, connections, utility, SearchResult

from agile.db.vector import BaseEmbedModel
from agile.utils import LogHelper

logger = LogHelper.get_logger()


@unique
class MilvusIndexType(Enum):
    """
    Milvus 索引类型枚举类
    每个枚举值对应 Milvus 官方定义的 index_type 字符串，注释说明适用场景
    """
    # ====================== 标量索引 ======================
    STL_RAW = ("STL_RAW", False)
    """标量原生索引：适用于整数/浮点数/字符串等标量字段，默认推荐"""

    INVERTED = ("INVERTED", False)
    """倒排索引：适用于字符串/关键词检索，支持模糊匹配"""

    # ====================== 向量索引 - 基础型 ======================
    FLAT = ("FLAT", True)
    """暴力检索：精度100%，速度最慢，无索引构建开销，适合小数据集（<10万条）"""

    # ====================== 向量索引 - IVF 系列（倒排文件） ======================
    IVF_FLAT = ("IVF_FLAT", True)
    """倒排文件+暴力：精度高，速度比FLAT快，平衡型首选（10万~1000万条）"""

    IVF_SQ8 = ("IVF_SQ8", True)
    """倒排文件+标量量化：比IVF_FLAT节省内存，精度略降"""

    IVF_PQ = ("IVF_PQ", True)
    """倒排文件+乘积量化：内存占用极低，精度中等，适合大数据量（1000万+）"""

    # ====================== 向量索引 - HNSW 系列（实时检索首选） ======================
    HNSW = ("HNSW", True)
    """分层导航小世界：速度极快，精度高，内存占用较高，实时检索首选（10万~1亿条）"""

    RHNSW_FLAT = ("RHNSW_FLAT", True)
    """HNSW+FLAT：比HNSW精度更高，速度略慢"""

    RHNSW_SQ = ("RHNSW_SQ", True)
    """HNSW+标量量化：HNSW变种，节省内存"""

    RHNSW_PQ = ("RHNSW_PQ", True)
    """HNSW+乘积量化：HNSW变种，内存占用最低"""

    # ====================== 向量索引 - 其他类型 ======================
    ANNOY = ("ANNOY", True)
    """近似近邻检索：轻量级，适合小数据集，跨平台兼容性好"""

    DISKANN = ("DISKANN", True)
    """磁盘索引：适合超大数据量（亿级），减少内存占用（Milvus 2.2+支持）"""

    def __init__(self, index_type_value: str, is_vector: bool):
        """
        枚举初始化方法
        :param index_type_value: Milvus 官方定义的 index_value 字符串
        :param is_vector: 是否为向量索引（True=向量索引，False=标量索引）
        """
        self.index_type_value = index_type_value
        self.is_vector = is_vector

    @classmethod
    def is_vector_index(cls, index_type: "MilvusIndexType | str") -> bool:
        """
        辅助方法：判断传入的索引类型是否为向量索引
        :param index_type: 索引类型字符串（如 "FLAT"）或枚举值
        :return: True=向量索引，False=标量索引
        """
        if index_type is None:
            return False

        if isinstance(index_type, cls):
            return index_type.is_vector

        if isinstance(index_type, str):
            index_type_str = index_type.strip().upper()
            # 遍历枚举成员，匹配 index_type_value
            for enum_member in cls:
                if enum_member.index_type_value == index_type_str:
                    return enum_member.is_vector

        return False

    @classmethod
    def is_scalar_index(cls, index_type: "MilvusIndexType | str") -> bool:
        """
        辅助方法：判断传入的索引类型是否为标量索引
        """
        # 先验证输入是否为合法的索引类型，再取反
        if not cls.is_valid_index_type(index_type):
            return False
        return not cls.is_vector_index(index_type)

    @classmethod
    def is_valid_index_type(cls, index_type: "MilvusIndexType | str") -> bool:
        """
        扩展方法：验证输入是否为合法的 Milvus 索引类型
        :return: True=合法，False=非法
        """
        if index_type is None:
            return False

        if isinstance(index_type, cls):
            return True

        if isinstance(index_type, str):
            clean_index_str = index_type.strip().upper()
            return any(enum_member.index_type_value == clean_index_str for enum_member in cls)

        return False

    @classmethod
    def normalize_index_type(cls, index_type: "MilvusIndexType | str") -> "MilvusIndexType":
        """
        将字符串或枚举值归一化为 MilvusIndexType
        """
        if isinstance(index_type, cls):
            return index_type

        if isinstance(index_type, str):
            clean_index_str = index_type.strip().upper()
            for enum_member in cls:
                if enum_member.index_type_value == clean_index_str:
                    return enum_member

        raise ValueError(f"Invalid Milvus index type: {index_type}")


@dataclass(frozen=True, slots=True)
class MilvusIndexSpec:
    """
    Milvus 集合索引规格
    """
    field_name: str
    index_type: MilvusIndexType | str
    index_params: dict[str, Any] | None = None
    index_name: str | None = None


class MilvusManager:
    """
    Milvus 数据库管理器
    """

    def __init__(
            self,
            *,
            uri: str,
            token: str,
            embedding_model: BaseEmbedModel,
            primary_field: str = "id",
            text_field: str = "text",
            vector_field: str = "vector",
            default_collection_name: str = None,
            default_field_schemas: List[FieldSchema] = None,
            default_index_specs: List[MilvusIndexSpec | dict[str, Any]] = None,
            index_type: MilvusIndexType = MilvusIndexType.IVF_FLAT,
            metric_type="L2",
            params_nlist: int = 128,
            params_nprobe: int = 10,
            vector_dim: int = 1536,
            search_timeout: float = 30.0
    ):
        """
        MilvusManager 构造函数
        :param uri: Milvus URI
        :param token: Milvus 访问令牌
        :param embedding_model: 嵌入模型实例
        :param primary_field: 主键字段名称
        :param text_field: 文本字段名称
        :param vector_field: 向量字段名称
        :param index_type: 索引类型
        :param metric_type: 距离度量类型
        :param params_nlist: 索引参数-聚类总数
        :param params_nprobe: 搜索参数-探测的聚类中心数量，其值的大小直接影响检索效果，值不能超过创建 IVF 索引时设置的 nlist（聚类总数）
        :param vector_dim: 向量维度
        :param search_timeout: 搜索超时时间
        """

        # 参数验证
        if not uri or not uri.strip():
            raise ValueError("URI cannot be empty")
        if not token or not token.strip():
            raise ValueError("Token cannot be empty")
        if vector_dim <= 0:
            raise ValueError("vector_dim must be positive")
        if params_nprobe > params_nlist:
            raise ValueError("params_nprobe cannot exceed params_nlist")
        if search_timeout <= 0:
            raise ValueError("search_timeout must be positive")

        # 初始化嵌入模型
        self.embedding_model = embedding_model

        # 属性字段
        self.primary_field = primary_field
        self.text_field = text_field
        self.vector_field = vector_field

        # 参数字段
        self.index_type = index_type
        self.metric_type = metric_type
        self.params_nlist = params_nlist
        self.params_nprobe = params_nprobe
        self.vector_dim = vector_dim
        self.search_timeout = search_timeout

        # 缓存集合：已初始化的 collection（已检查存在性）
        self._initialized_collections: Set[str] = set()
        # 缓存集合：已加载到内存的 collection
        self._loaded_collections: Set[str] = set()

        # 索引参数
        self.index_params = {
            "index_type": self.index_type.index_type_value,
            "metric_type": self.metric_type,
            "params": {"nlist": self.params_nlist}
        }

        # 搜索参数
        self.search_params = {
            "metric_type": self.metric_type,
            "params": {"nprobe": self.params_nprobe}
        }

        # 初始化 Milvus 客户端 pymilvus
        self.milvus_client = MilvusClient(uri=uri, token=token)

        # 默认集合名称
        self.default_collection_name = default_collection_name
        self.default_field_schemas = [
            FieldSchema(name=self.primary_field, dtype=DataType.VARCHAR, is_primary=True, max_length=65535),
            FieldSchema(name=self.text_field, dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name=self.vector_field, dtype=DataType.FLOAT_VECTOR, dim=self.vector_dim),
            FieldSchema(name="metadata", dtype=DataType.JSON),
        ] if not default_field_schemas else default_field_schemas
        self.default_index_specs = self._normalize_index_specs(default_index_specs)

        # 建立连接
        connections.connect(alias="default", uri=uri, token=token)

    async def ensure_collection_ready(self,
                                      collection_name: str = None,
                                      field_schemas: List[FieldSchema] = None,
                                      index_specs: List[MilvusIndexSpec | dict[str, Any]] = None):
        """
        预初始化 collection：确保存在、已加载、已就绪
        应在应用启动时调用，而不是在每次查询时调用
        :param collection_name: 集合名称
        :param field_schemas: 可选的字段模式列表，如果提供则使用，否则使用默认字段定义
        :param index_specs: 额外索引规格列表，默认会先创建向量索引，再创建这里传入的索引
        :return:
        """
        try:
            # 使用默认集合名称
            collection_name = self._get_collection_name(collection_name)
            # 确保集合存在
            self._ensure_collection_exists(
                collection_name=collection_name,
                field_schemas=field_schemas,
                index_specs=index_specs,
            )

            # 获取集合对象并加载到内存
            collection = Collection(name=collection_name)
            if collection_name not in self._loaded_collections:
                collection.load()
                self._loaded_collections.add(collection_name)
                logger.info(f"Collection '{collection_name}' loaded into memory")

            logger.info(f"Collection '{collection_name}' is ready")
        except Exception as e:
            logger.error(f"Failed to ensure collection '{collection_name}' ready: {str(e)}")
            raise e

    async def insert(self,
                     documents: List[Union[Document, dict]],
                     collection_name: str = None):
        """
        插入文档到集合。
        - 若元素为 dict：按原样直接插入（调用方需保证字段与 schema 匹配）
        - 若元素为 langchain Document：按 primary/text/vector/metadata 结构转换后插入
        :param collection_name: 集合名称
        :param documents: Document 或 dict 的列表
        :return: None
        """
        try:
            # 获取集合名称
            collection_name = self._get_collection_name(collection_name)
            # 获取集合对象
            collection = await self.get_collection(collection_name)
            # 如果集合不存在，抛出异常
            if not collection:
                raise ValueError(f"Collection '{collection_name}' does not exist. Please ensure it is created and ready before inserting documents.")
            # 分流数据：dict 直接插入；Document 走向量化流程
            dict_documents: List[dict] = []
            doc_ids: List[str] = []
            texts: List[str] = []
            metadata_list: List[dict] = []

            for item in documents:
                if isinstance(item, dict):
                    dict_documents.append(item)
                    continue

                if not isinstance(item, Document):
                    raise TypeError(f"Unsupported document type: {type(item).__name__}")

                _id = getattr(item, "id", None) or getattr(item, self.primary_field, None)
                text = getattr(item, "page_content", None)
                metadata = getattr(item, "metadata", None) or {}

                if not _id:
                    _id = str(uuid.uuid4())

                if text is None:
                    # 将空内容视为空字符串，避免嵌入器报错；调用方应负责文本有效性
                    text = ""

                if not isinstance(metadata, dict):
                    metadata = {"value": metadata}

                doc_ids.append(str(_id))
                texts.append(text)
                metadata_list.append(metadata)

            # dict 直接插入
            if dict_documents:
                for dict_document in dict_documents:
                    embedding = await self.embedding_model.embed(dict_document.get(self.text_field) or "")
                    dict_document.setdefault(self.vector_field, embedding)
                collection.insert(dict_documents)

            # Document 转 schema 顺序结构并插入
            if texts:
                embeddings = await self.embedding_model.embed_batch(texts)
                # 准备插入数据（顺序必须与 schema 定义一致）
                # Schema 顺序: primary_field -> text_field -> vector_field -> metadata
                entities = [doc_ids, texts, embeddings, metadata_list]
                collection.insert(entities)

            collection.flush()  # 刷新确保数据持久化

            logger.info(f"Successfully inserted {len(documents)} documents into collection {collection_name}")
        except Exception as e:
            logger.error(f"Failed to insert documents into Milvus: {str(e)}")
            raise e

    async def search(self,
                     query: str,
                     *,
                     collection_name: str = None,
                     filter_expr: str = None,
                     output_fields: List[str] = None,
                     search_params: dict[str, Any] = None,
                     top_k: int = 5,
                     timeout: float = None) -> SearchResult | list:
        """
        在 Milvus 集合中进行异步相似度搜索
        :param query: 查询语句
        :param collection_name: 集合名称
        :param filter_expr: 过滤表达式
        :param output_fields: 要返回的字段列表，如果为 None 则返回所有字段
        :param search_params: 搜索参数字典，如果为 None 则使用默认搜索参数
        :param top_k: 返回数量
        :param timeout: 超时时间（秒）
        :return: 搜索结果
        """
        try:
            # 获取集合名称
            collection_name = self._get_collection_name(collection_name)

            # 获取集合对象
            collection = await self.get_collection(collection_name)
            if not collection:
                raise ValueError(f"Collection '{collection_name}' does not exist. Please ensure it is created and ready before performing search.")

            # 生成查询嵌入向量
            query_embedding = await self.embedding_model.embed(query)

            # 设置超时时间
            timeout = timeout or self.search_timeout

            def _do_search():
                """同步搜索函数，在线程池中执行"""
                return collection.search(
                    data=[query_embedding],
                    anns_field=self.vector_field,
                    param=search_params if search_params else self.search_params,
                    limit=top_k,
                    expr=filter_expr,
                    output_fields=output_fields or ["*"],
                    timeout=timeout
                )

            # 使用 asyncio.to_thread 运行同步函数，返回原始 SearchResult
            results = await asyncio.to_thread(_do_search)

            # 返回原始结果，使用者如需 Document 列表可以调用 self.trans_to_documents(results)
            logger.info(f"Async search completed for collection '{collection_name}'")
            return results

        except asyncio.TimeoutError:
            logger.error(f"Milvus search timeout after {timeout}s for query: {query[:50]}...")
            # 返回空结果而不是抛出异常，避免影响整体流程
            return []
        except Exception as e:
            logger.error(f"Failed to perform async search in Milvus: {str(e)}", exc_info=True)
            return []

    async def get_collection(self, collection_name: str) -> Collection | None:
        """
        获取 collection 对象
        :param collection_name: 集合名称
        :return: Collection 对象
        """
        # 如果已初始化，直接获取（不再检查是否存在）
        if collection_name in self._initialized_collections:
            collection = Collection(name=collection_name)
            # 如果未加载，则加载（通常第一次查询时需要）
            if collection_name not in self._loaded_collections:
                collection.load()
                self._loaded_collections.add(collection_name)
            return collection
        # 如果未初始化，返回 None
        return None

    async def create_collection(self,
                                collection_name: str = None,
                                *,
                                collection_desc: str = None,
                                field_schemas: List[FieldSchema] = None,
                                index_specs: List[MilvusIndexSpec | dict[str, Any]] = None):
        """
        创建集合
        :param collection_name: 集合名称
        :param collection_desc: 集合描述
        :param field_schemas: 可选的字段模式列表，如果提供则使用，否则使用默认字段定义
        :param index_specs: 额外索引规格列表，默认会先创建向量索引，再创建这里传入的索引
        :return:
        """
        try:
            collection_name = self._get_collection_name(collection_name)
            if utility.has_collection(collection_name):
                logger.warning(f"Collection {collection_name} already exists, cannot create.")
                return

            # 创建集合
            self._ensure_collection_exists(
                collection_name=collection_name,
                collection_desc=collection_desc,
                field_schemas=field_schemas,
                index_specs=index_specs,
            )
        except Exception as e:
            logger.error(f"Failed to create collection {collection_name}: {str(e)}")
            raise e

    async def delete_collection(self, collection_name: str):
        """
        删除集合
        :param collection_name: 集合名称
        :return:
        """
        try:
            if utility.has_collection(collection_name):
                utility.drop_collection(collection_name)
                # 从缓存中移除
                self._initialized_collections.discard(collection_name)
                self._loaded_collections.discard(collection_name)
                logger.info(f"Successfully deleted collection: {collection_name}")
            else:
                logger.warning(f"Collection {collection_name} does not exist, cannot delete.")
        except Exception as e:
            logger.error(f"Failed to delete collection {collection_name}: {str(e)}")
            raise e

    async def get_collection_count(self, collection_name: str = None) -> int:
        """
        获取集合中的元素数量
        :param collection_name: 集合名称，如果为 None 则使用默认集合
        :return: 集合中的元素数量
        """
        try:
            # 获取集合名称
            collection_name = self._get_collection_name(collection_name)
            # 获取集合对象
            collection = await self.get_collection(collection_name)
            # 获取元素数量
            count = collection.num_entities
            logger.info(f"Collection '{collection_name}' has {count} entities")
            return count
        except Exception as e:
            logger.error(f"Failed to get count for collection {collection_name}: {str(e)}")
            raise e

    async def delete_by_ids(self,
                            ids: List[str],
                            collection_name: str = None):
        """
        根据主键 ID 删除文档
        :param ids: 要删除的文档 ID 列表
        :param collection_name: 集合名称
        :return:
        """
        try:
            if not ids:
                logger.warning("No IDs provided for deletion")
                return

            # 获取集合名称
            collection_name = self._get_collection_name(collection_name)
            # 获取集合对象
            collection = await self.get_collection(collection_name)
            if not collection:
                raise ValueError(f"Collection '{collection_name}' does not exist.")

            # 构建删除表达式
            ids_str = ", ".join([f"'{id_}'" for id_ in ids])
            expr = f"{self.primary_field} in [{ids_str}]"

            # 执行删除
            collection.delete(expr)
            collection.flush()

            logger.info(f"Successfully deleted {len(ids)} documents from collection {collection_name}")
        except Exception as e:
            logger.error(f"Failed to delete documents: {str(e)}")
            raise e

    async def get_by_ids(self,
                         ids: List[str],
                         collection_name: str = None,
                         output_fields: List[str] = None, ) -> List[Document]:
        """
        根据主键 ID 批量查询文档
        :param ids: 要查询的文档 ID 列表
        :param collection_name: 集合名称
        :param output_fields: 要返回的字段列表，如果为 None 则返回所有字段
        :return: 文档列表
        """
        try:
            if not ids:
                return []

            # 获取集合名称
            collection_name = self._get_collection_name(collection_name)
            # 获取集合对象
            collection = await self.get_collection(collection_name)
            if not collection:
                raise ValueError(f"Collection '{collection_name}' does not exist.")

            # 构建查询表达式
            ids_str = ", ".join([f"'{id_}'" for id_ in ids])
            expr = f"{self.primary_field} in [{ids_str}]"

            # 执行查询
            results = collection.query(
                expr=expr,
                output_fields=output_fields or ["*"]
            )

            # 转换为 Document 对象
            documents = []
            for result in results:
                doc = Document(
                    id=result.get(self.primary_field),
                    page_content=result.get(self.text_field, ""),
                    metadata={
                        self.primary_field: result.get(self.primary_field),
                        **result.get("metadata", {})
                    }
                )
                documents.append(doc)

            logger.info(f"Retrieved {len(documents)} documents by IDs")
            return documents

        except Exception as e:
            logger.error(f"Failed to get documents by IDs: {str(e)}")
            return []

    async def clear_collection(self, collection_name: str):
        """
        清空集合中的所有数据，但保留集合结构
        :param collection_name: 集合名称
        :return:
        """
        try:
            # 获取集合名称
            collection_name = self._get_collection_name(collection_name)
            # 获取集合对象
            collection = await self.get_collection(collection_name)
            if not collection:
                raise ValueError(f"Collection '{collection_name}' does not exist.")

            # 删除所有数据（使用空过滤条件删除所有记录）
            collection.delete(expr=f"{self.primary_field} != ''")
            collection.flush()

            logger.info(f"Successfully cleared all data from collection {collection_name}")
        except Exception as e:
            logger.error(f"Failed to clear collection {collection_name}: {str(e)}")
            raise e

    async def get_collection_stats(self, collection_name: str = None) -> dict:
        """
        获取集合详细统计信息
        :param collection_name: 集合名称
        :return: 统计信息字典
        """
        try:
            # 获取集合名称
            collection_name = self._get_collection_name(collection_name)
            # 获取集合对象
            collection = await self.get_collection(collection_name)
            if not collection:
                raise ValueError(f"Collection '{collection_name}' does not exist.")

            # 获取统计信息
            stats = {
                "name": collection_name,
                "num_entities": collection.num_entities,
                "num_shards": collection.num_shards,
                "is_empty": collection.is_empty,
                "schema": {
                    "fields": [
                        {
                            "name": field.name,
                            "type": str(field.dtype),
                            "is_primary": field.is_primary
                        }
                        for field in collection.schema.fields
                    ]
                },
                "indexes": [
                    {
                        "field_name": index.field_name,
                        "index_name": index.index_name,
                        "params": index.params
                    }
                    for index in collection.indexes
                ]
            }

            logger.info(f"Retrieved stats for collection {collection_name}")
            return stats

        except Exception as e:
            logger.error(f"Failed to get collection stats: {str(e)}")
            raise e

    @staticmethod
    def health_check() -> bool:
        """
        检查连接是否正常
        :return: True 表示连接正常，False 表示连接异常
        """
        try:
            utility.list_collections()
            logger.debug("Milvus health check passed")
            return True
        except Exception as e:
            logger.error(f"Milvus health check failed: {str(e)}")
            return False

    def close(self):
        """
        关闭连接并清理资源
        """
        try:
            connections.disconnect(alias="default")
            self._initialized_collections.clear()
            self._loaded_collections.clear()
            logger.info("Milvus connection closed and resources cleared")
        except Exception as e:
            logger.error(f"Failed to close Milvus connection: {str(e)}")

    @staticmethod
    async def list_collections():
        """
        列出所有集合
        :return: 集合名称列表
        """
        try:
            collections = utility.list_collections()
            logger.info(f"Current collections in Milvus: {collections}")
            return collections
        except Exception as e:
            logger.error(f"Failed to list collections in Milvus: {str(e)}")
            raise e

    def _get_collection_name(self, collection_name: str = None) -> str:
        """
        获取集合名称，如果未提供则使用默认集合名称
        :param collection_name: 集合名称
        :return: 集合名称
        """
        normalized_collection_name = collection_name or self.default_collection_name
        if not isinstance(normalized_collection_name, str) or not normalized_collection_name.strip():
            raise ValueError("Collection name must be provided either as an argument or set as default_collection_name")
        return normalized_collection_name.strip()

    def _create_collection_schema(self,
                                  collection_desc: str = None,
                                  field_schemas: List[FieldSchema] = None) -> CollectionSchema:
        """
        创建集合模式
        :param collection_desc: 集合描述
        :param field_schemas: 可选的字段模式列表，如果提供则使用，否则使用默认字段定义
        :return: CollectionSchema 对象
        """
        # 定义字段
        fields = field_schemas or self.default_field_schemas
        # 创建集合模式
        return CollectionSchema(
            fields=fields,
            description=collection_desc or ""
        )

    def _build_default_index_spec(self) -> MilvusIndexSpec:
        """
        构建默认向量索引规格
        """
        return MilvusIndexSpec(
            field_name=self.vector_field,
            index_type=self.index_type,
            index_params=self.index_params,
        )

    def _normalize_index_spec(self, index_spec: MilvusIndexSpec | dict[str, Any]) -> MilvusIndexSpec:
        """
        归一化单个索引规格
        """
        if isinstance(index_spec, MilvusIndexSpec):
            spec = index_spec
        elif isinstance(index_spec, dict):
            field_name = index_spec.get("field_name")
            index_type = index_spec.get("index_type")
            index_name = index_spec.get("index_name") or index_spec.get("name") or field_name
            spec = MilvusIndexSpec(
                field_name=cast(str, field_name),
                index_type=cast(MilvusIndexType | str, index_type),
                index_params=index_spec.get("index_params", index_spec.get("params")),
                index_name=index_name,
            )
        else:
            raise TypeError(f"Unsupported index spec type: {type(index_spec).__name__}")

        if not isinstance(spec.field_name, str) or not spec.field_name.strip():
            raise ValueError("Index spec field_name cannot be empty")

        if not MilvusIndexType.is_valid_index_type(spec.index_type):
            raise ValueError(f"Invalid Milvus index type: {spec.index_type}")

        if spec.index_params is not None and not isinstance(spec.index_params, dict):
            raise TypeError("Index spec index_params must be a dict or None")

        return MilvusIndexSpec(
            field_name=spec.field_name.strip(),
            index_type=MilvusIndexType.normalize_index_type(spec.index_type),
            index_params=spec.index_params,
        )

    def _normalize_index_specs(self, index_specs: List[MilvusIndexSpec | dict[str, Any]] = None) -> list[MilvusIndexSpec]:
        """
        归一化索引规格列表
        """
        if not index_specs:
            return []

        return [self._normalize_index_spec(index_spec) for index_spec in index_specs]

    @staticmethod
    def _is_vector_dtype(dtype: Any) -> bool:
        """
        判断字段类型是否为向量类型
        """
        dtype_name = getattr(dtype, "name", "") or str(dtype)
        return "VECTOR" in str(dtype_name).upper()

    def _validate_index_specs(self, index_specs: List[MilvusIndexSpec], field_schemas: List[FieldSchema]):
        """
        校验索引规格是否可用于当前字段定义
        """
        field_type_map = {field.name: field.dtype for field in (field_schemas or [])}
        seen_field_names: Set[str] = set()

        for index_spec in index_specs:
            if index_spec.field_name in seen_field_names:
                raise ValueError(f"Duplicate index spec for field '{index_spec.field_name}'")
            seen_field_names.add(index_spec.field_name)

            index_type = MilvusIndexType.normalize_index_type(index_spec.index_type)
            field_dtype = field_type_map.get(index_spec.field_name)

            if field_type_map and field_dtype is None:
                raise ValueError(f"Field '{index_spec.field_name}' does not exist in collection schema")

            if field_dtype is not None:
                field_is_vector = self._is_vector_dtype(field_dtype)
                if field_is_vector != index_type.is_vector:
                    raise ValueError(
                        f"Index type '{index_type.index_type_value}' is not compatible with field '{index_spec.field_name}'"
                    )

            if index_spec.field_name == self.vector_field and not index_type.is_vector:
                raise ValueError(
                    f"Field '{index_spec.field_name}' is the vector field and must use a vector index"
                )

    def _build_index_params(self, index_spec: MilvusIndexSpec) -> dict[str, Any]:
        """
        组装 Milvus create_index 所需参数
        """
        index_type = MilvusIndexType.normalize_index_type(index_spec.index_type)

        if index_spec.field_name == self.vector_field and index_type == self.index_type and not index_spec.index_params:
            return dict(self.index_params)

        if index_type.is_vector and not index_spec.index_params:
            raise ValueError(
                f"Vector index spec for field '{index_spec.field_name}' must provide index_params"
            )

        index_params: dict[str, Any] = {"index_type": index_type.index_type_value}
        if index_type.is_vector:
            index_params["metric_type"] = self.metric_type

        if index_spec.index_params:
            index_params.update(index_spec.index_params)

        return index_params

    def _create_collection_indexes(
            self,
            collection: Collection,
            *,
            field_schemas: List[FieldSchema],
            index_specs: List[MilvusIndexSpec] = None,
    ):
        """
        为集合创建索引
        """
        resolved_index_specs = [self._build_default_index_spec(), *self.default_index_specs]
        if index_specs:
            resolved_index_specs.extend(index_specs)

        self._validate_index_specs(resolved_index_specs, field_schemas)

        for index_spec in resolved_index_specs:
            # pass index_name if provided (pymilvus supports optional index_name)
            collection.create_index(
                field_name=index_spec.field_name,
                index_params=self._build_index_params(index_spec),
                index_name=index_spec.index_name,
            )

    def _ensure_collection_exists(self,
                                  *,
                                  collection_name: str = None,
                                  collection_desc: str = None,
                                  field_schemas: List[FieldSchema] = None,
                                  index_specs: List[MilvusIndexSpec | dict[str, Any]] = None):
        """
        确保集合存在，如果不存在则创建
        :param collection_name: 集合名称
        :param collection_desc: 集合描述
        :param field_schemas: 可选的字段模式列表，如果提供则使用，否则使用默认字段定义
        :param index_specs: 额外索引规格列表
        :return:
        """
        # 使用缓存避免重复检查
        collection_name = self._get_collection_name(collection_name)
        if collection_name in self._initialized_collections:
            return

        resolved_field_schemas = field_schemas or self.default_field_schemas
        normalized_index_specs = self._normalize_index_specs(index_specs)

        if not utility.has_collection(collection_name):
            # 创建集合
            schema = self._create_collection_schema(collection_desc, resolved_field_schemas)
            collection = Collection(
                name=collection_name,
                schema=schema
            )
            # 创建索引
            self._create_collection_indexes(
                collection,
                field_schemas=resolved_field_schemas,
                index_specs=normalized_index_specs,
            )
            logger.info(f"Created new collection: {collection_name}")

        # 标记为已初始化
        self._initialized_collections.add(collection_name)

    def trans_to_documents(self, results: SearchResult | list) -> list[Document]:
        """
        将 Milvus 搜索结果包装为 Document 对象
        :param results: 搜索结果
        :return: 包装后的文档列表
        """
        documents = []
        for hits in results:
            for hit in hits:
                primary_key = hit.entity.get(self.primary_field)
                # 将 entity 转为字典
                entity_data = hit.entity.get("entity")
                metadata = {
                    self.primary_field: primary_key,
                    "score": hit.distance,
                    **entity_data,
                }
                doc = Document(
                    id=primary_key,
                    page_content=entity_data.get(self.text_field),
                    metadata=metadata
                )
                documents.append(doc)
        return documents

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        self.close()
