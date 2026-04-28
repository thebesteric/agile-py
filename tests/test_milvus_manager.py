import asyncio
import unittest
import sys
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch, AsyncMock

from langchain_core.documents import Document
from pymilvus import FieldSchema, DataType

SRC_PATH = Path(__file__).resolve().parents[1] / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from agile.db.vector.base.base_embed_model import BaseEmbedModel
from agile.db.vector.milvus.milvus_manager import (
    MilvusCollectionConfig,
    MilvusIndexSpec,
    MilvusIndexType,
    MilvusManager,
)


class DummyEmbedModel(BaseEmbedModel):
    def __init__(self, /, dim: int = 2, **data):
        super().__init__(dim=dim, **data)

    async def embed(self, text: str, model: str = None, dim: int = None):
        target_dim = cast(int, self.dim if dim is None else dim)
        return [0.0] * target_dim

    async def embed_batch(self, texts: list[str], model: str = None, dim: int = None):
        return [await self.embed(_) for _ in texts]


class TestMilvusManager(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.manager = MilvusManager(
            uri="http://localhost:19530",
            token="root:Milvus",
            embedding_model=DummyEmbedModel(dim=1536),
            default_collection_name="docs",
            # default_field_schemas=[
            #     FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=65535),
            #     FieldSchema(name="question", dtype=DataType.VARCHAR, max_length=65535),
            #     FieldSchema(name="sql", dtype=DataType.VARCHAR, max_length=65535),
            #     FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=1536),
            #     FieldSchema(name="metadata", dtype=DataType.JSON),
            # ],
            default_text_field="question",
            default_vector_field="vector",
            allow_dynamic_field=True,
            vector_dim=1536,
        )

    def test(self):
        asyncio.run(
            self.manager.ensure_collection_ready(
                collection_name="test",
                field_schemas=[
                    FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=65535),
                    FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
                    FieldSchema(name="sql", dtype=DataType.VARCHAR, max_length=65535),
                    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=1536),
                ],
                collection_config=MilvusCollectionConfig(
                    primary_field="id",
                    text_field="text",
                    vector_field="embedding",
                ),
                allow_dynamic_field=False
            )
        )

        asyncio.run(
            self.manager.insert(
                [{
                    "id": "1",
                    "text": "q1",
                    "sql": "insert",
                    "body": "11"
                }],
                collection_name="test"
            )
        )


if __name__ == "__main__":
    unittest.main()
