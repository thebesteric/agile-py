import asyncio
import uuid
from enum import Enum, unique
from typing import List, Set

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
            default_collection_name: str = None,
            primary_field: str = "id",
            text_field: str = "text",
            vector_field: str = "vector",
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
        # 默认集合名称
        self.default_collection_name = default_collection_name

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

        # 建立连接
        connections.connect(alias="default", uri=uri, token=token)

    def _get_collection_name(self, collection_name: str | None = None) -> str:
        """
        获取集合名称，如果未提供则使用默认集合名称
        :param collection_name: 集合名称
        :return: 集合名称
        """
        collection_name = collection_name or self.default_collection_name
        if not (collection_name and collection_name.strip()):
            raise ValueError("Collection name must be provided either as an argument or set as default_collection_name")
        return collection_name.strip()

    def _create_collection_schema(self, fields: List[FieldSchema] = None) -> CollectionSchema:
        """
        创建集合模式
        :return: CollectionSchema 对象
        """
        # 定义字段
        fields = [
            FieldSchema(name=self.primary_field, dtype=DataType.VARCHAR, is_primary=True, max_length=65535),
            FieldSchema(name=self.text_field, dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name=self.vector_field, dtype=DataType.FLOAT_VECTOR, dim=self.vector_dim),
            FieldSchema(name="metadata", dtype=DataType.JSON),
        ] if not fields else fields

        # 创建集合模式
        schema = CollectionSchema(
            fields=fields,
            description="Milvus collection for document storage and similarity search"
        )
        return schema

    def _ensure_collection_exists(self, collection_name: str | None = None):
        """
        确保集合存在，如果不存在则创建
        :param collection_name: 集合名称
        :return:
        """
        # 使用缓存避免重复检查
        collection_name = self._get_collection_name(collection_name)
        if collection_name in self._initialized_collections:
            return

        if not utility.has_collection(collection_name):
            # 创建集合
            schema = self._create_collection_schema()
            collection = Collection(
                name=collection_name,
                schema=schema
            )
            # 创建索引
            collection.create_index(
                field_name=self.vector_field,
                index_params=self.index_params
            )
            logger.info(f"Created new collection: {collection_name}")

        # 标记为已初始化
        self._initialized_collections.add(collection_name)

    async def ensure_collection_ready(self, collection_name: str | None = None):
        """
        预初始化 collection：确保存在、已加载、已就绪
        应在应用启动时调用，而不是在每次查询时调用
        :param collection_name: 集合名称
        :return:
        """
        try:
            # 使用默认集合名称
            collection_name = self._get_collection_name(collection_name)
            # 确保集合存在
            self._ensure_collection_exists(collection_name)

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

    def get_collection(self, collection_name: str) -> Collection:
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

        # 如果未初始化，会先创建集合（如果不存在），然后获取并加载
        self._ensure_collection_exists(collection_name)
        collection = Collection(name=collection_name)
        if collection_name not in self._loaded_collections:
            collection.load()
            self._loaded_collections.add(collection_name)
        return collection

    async def insert_documents(self, documents: List[Document], collection_name: str | None = None):
        """
        插入文档到集合
        :param collection_name: 集合名称
        :param documents: 文档列表
        :return:
        """
        try:
            # 获取集合名称
            collection_name = self._get_collection_name(collection_name)
            # 确保集合存在（数据导入时可能需要创建）
            self._ensure_collection_exists(collection_name)
            # 获取集合对象
            collection = self.get_collection(collection_name)

            # 准备数据
            doc_ids = [str(uuid.uuid4()) for _ in documents]
            texts = [doc.page_content for doc in documents]
            metadatas = [doc.metadata for doc in documents]

            # 生成嵌入向量
            embeddings = await self.embedding_model.embed_batch(texts)

            # 准备插入数据
            entities = [
                doc_ids,
                embeddings,
                texts,
                metadatas
            ]

            # 插入数据
            collection.insert(entities)
            collection.flush()  # 刷新确保数据持久化

            logger.info(f"Successfully inserted {len(documents)} documents into collection {collection_name}")
        except Exception as e:
            logger.error(f"Failed to insert documents into Milvus: {str(e)}")
            raise e

    async def async_search(self, query: str, collection_name: str | None = None, top_k: int = 5, timeout: float = None) -> list[Document]:
        """
        在 Milvus 集合中进行异步相似度搜索
        :param collection_name: 集合名称
        :param query: 查询语句
        :param top_k: 返回数量
        :param timeout: 超时时间（秒）
        :return: 搜索结果
        """
        try:
            # 获取集合名称
            collection_name = self._get_collection_name(collection_name)
            # 设置超时时间
            timeout = timeout or self.search_timeout
            # 获取集合对象
            collection = self.get_collection(collection_name)
            # 生成查询嵌入向量
            query_embedding = await self.embedding_model.embed(query)

            def _do_search():
                """同步搜索函数，在线程池中执行"""
                return collection.search(
                    data=[query_embedding],
                    anns_field=self.vector_field,
                    param=self.search_params,
                    limit=top_k,
                    output_fields=["*"],
                    timeout=timeout
                )

            # 使用 asyncio.to_thread 运行同步函数
            results = await asyncio.to_thread(_do_search)

            # 处理搜索结果
            documents = self._package_documents(results)

            logger.info(f"Async search completed, found {len(documents)} results")
            return documents

        except asyncio.TimeoutError:
            logger.error(f"Milvus search timeout after {timeout}s for query: {query[:50]}...")
            # 返回空结果而不是抛出异常，避免影响整体流程
            return []
        except Exception as e:
            logger.error(f"Failed to perform async search in Milvus: {str(e)}", exc_info=True)
            return []

    def sync_search(self, query: str, collection_name: str | None = None, top_k: int = 5, timeout: float = None) -> list[Document]:
        """
        在 Milvus 集合中进行同步相似度搜索
        :param collection_name: 集合名称
        :param query: 查询语句
        :param top_k: 返回数量
        :param timeout: 超时时间（秒）
        :return: 搜索结果
        """
        try:
            # 获取集合名称
            collection_name = self._get_collection_name(collection_name)
            # 设置超时时间
            timeout = timeout or self.search_timeout
            # 获取集合对象
            collection = self.get_collection(collection_name)
            # 生成查询嵌入向量
            query_embedding = self.embedding_model.embed(query)

            # 执行搜索
            results = collection.search(
                data=[query_embedding],
                anns_field=self.vector_field,
                param=self.search_params,
                limit=top_k,
                output_fields=["*"],
                timeout=timeout
            )

            # 处理搜索结果
            documents = self._package_documents(results)

            logger.info(f"Sync search completed, found {len(documents)} results")
            return documents

        except Exception as e:
            logger.error(f"Failed to perform sync search in Milvus: {str(e)}")
            return []

    def _package_documents(self, results: SearchResult) -> list[Document]:
        """
        将 Milvus 搜索结果包装为 Document 对象
        :param results: 搜索结果
        :return: 包装后的文档列表
        """
        documents = []
        for hits in results:
            for hit in hits:
                primary_key = hit.entity.get(self.primary_field)
                doc = Document(
                    id=primary_key,
                    page_content=hit.entity.get(self.text_field),
                    metadata={
                        self.primary_field: primary_key,
                        "score": hit.distance,
                        **hit.entity.get("metadata", {})
                    }
                )
                documents.append(doc)
        return documents

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

    def get_collection_count(self, collection_name: str | None = None) -> int:
        """
        获取集合中的元素数量
        :param collection_name: 集合名称，如果为 None 则使用默认集合
        :return: 集合中的元素数量
        """
        try:
            # 获取集合名称
            collection_name = self._get_collection_name(collection_name)
            # 获取集合对象
            collection = self.get_collection(collection_name)
            # 获取元素数量
            count = collection.num_entities
            logger.info(f"Collection '{collection_name}' has {count} entities")
            return count
        except Exception as e:
            logger.error(f"Failed to get count for collection {collection_name}: {str(e)}")
            raise e

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
