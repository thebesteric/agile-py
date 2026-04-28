import unittest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

SRC_PATH = Path(__file__).resolve().parents[1] / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from agile.db.vector.base.base_embed_model import BaseEmbedModel
from agile.db.vector.milvus.milvus_manager import MilvusIndexSpec, MilvusIndexType, MilvusManager


class DummyEmbedModel(BaseEmbedModel):
    def __init__(self, /, dim: int = 2, **data):
        super().__init__(dim=dim, **data)

    async def embed(self, text: str, model: str = None, dim: int = None):
        return [0.0, 0.0]

    async def embed_batch(self, texts: list[str], model: str = None, dim: int = None):
        return [[0.0, 0.0] for _ in texts]


class TestMilvusManager(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        patcher_client = patch("agile.db.vector.milvus.milvus_manager.MilvusClient")
        patcher_connect = patch("agile.db.vector.milvus.milvus_manager.connections.connect")
        self.addCleanup(patcher_client.stop)
        self.addCleanup(patcher_connect.stop)
        self.mock_client = patcher_client.start()
        self.mock_connect = patcher_connect.start()

        self.manager = MilvusManager(
            uri="http://localhost:19530",
            token="root:Milvus",
            embedding_model=DummyEmbedModel(),
            default_collection_name="docs",
        )

    def test_ensure_collection_exists_creates_default_and_extra_indexes(self):
        collection_mock = MagicMock()
        collection_cls = patch("agile.db.vector.milvus.milvus_manager.Collection", return_value=collection_mock)
        has_collection = patch("agile.db.vector.milvus.milvus_manager.utility.has_collection", return_value=False)

        with collection_cls, has_collection:
            self.manager._ensure_collection_exists(
                collection_name="docs",
                field_schemas=self.manager.default_field_schemas,
                index_specs=[MilvusIndexSpec(field_name="metadata", index_type=MilvusIndexType.INVERTED)],
            )

        self.assertIn("docs", self.manager._initialized_collections)
        self.assertEqual(collection_mock.create_index.call_count, 2)

        first_call = collection_mock.create_index.call_args_list[0].kwargs
        second_call = collection_mock.create_index.call_args_list[1].kwargs

        self.assertEqual(first_call["field_name"], "vector")
        self.assertEqual(first_call["index_params"]["index_type"], "IVF_FLAT")
        self.assertEqual(second_call["field_name"], "metadata")
        self.assertEqual(second_call["index_params"]["index_type"], "INVERTED")

    def test_ensure_collection_exists_rejects_incompatible_index_type(self):
        collection_mock = MagicMock()
        collection_cls = patch("agile.db.vector.milvus.milvus_manager.Collection", return_value=collection_mock)
        has_collection = patch("agile.db.vector.milvus.milvus_manager.utility.has_collection", return_value=False)

        with collection_cls, has_collection:
            with self.assertRaisesRegex(ValueError, r"Index type 'FLAT' is not compatible with field 'metadata'"):
                self.manager._ensure_collection_exists(
                    collection_name="docs",
                    field_schemas=self.manager.default_field_schemas,
                    index_specs=[MilvusIndexSpec(field_name="metadata", index_type=MilvusIndexType.FLAT)],
                )

    async def test_create_collection_forwards_index_specs(self):
        index_specs = [MilvusIndexSpec(field_name="metadata", index_type=MilvusIndexType.INVERTED)]
        ensure_mock = MagicMock()

        with patch("agile.db.vector.milvus.milvus_manager.utility.has_collection", return_value=False), patch.object(
            self.manager, "_ensure_collection_exists", ensure_mock
        ):
            await self.manager.create_collection(
                "docs",
                collection_desc="demo",
                field_schemas=self.manager.default_field_schemas,
                index_specs=index_specs,
            )

        ensure_mock.assert_called_once_with(
            collection_name="docs",
            collection_desc="demo",
            field_schemas=self.manager.default_field_schemas,
            index_specs=index_specs,
        )

    async def test_create_collection_skips_existing_collection(self):
        ensure_mock = MagicMock()

        with patch("agile.db.vector.milvus.milvus_manager.utility.has_collection", return_value=True), patch.object(
            self.manager, "_ensure_collection_exists", ensure_mock
        ):
            await self.manager.create_collection("docs")

        ensure_mock.assert_not_called()

    async def test_ensure_collection_ready_forwards_index_specs(self):
        index_specs = [MilvusIndexSpec(field_name="metadata", index_type=MilvusIndexType.INVERTED)]
        ensure_mock = MagicMock()
        collection_mock = MagicMock()

        with patch.object(self.manager, "_ensure_collection_exists", ensure_mock), patch(
            "agile.db.vector.milvus.milvus_manager.Collection", return_value=collection_mock
        ):
            await self.manager.ensure_collection_ready(collection_name="docs", index_specs=index_specs)

        ensure_mock.assert_called_once_with(collection_name="docs", field_schemas=None, index_specs=index_specs)
        collection_mock.load.assert_called_once()


if __name__ == "__main__":
    unittest.main()

