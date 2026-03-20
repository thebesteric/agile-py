import os
import threading
import jieba
import tempfile

from whoosh.index import create_in, open_dir, exists_in
from whoosh.fields import Schema, TEXT, ID
from whoosh.qparser import QueryParser, OrGroup, GroupNode
from whoosh.analysis import Token, Analyzer
from whoosh.analysis import Tokenizer


class JiebaTokenizer(Tokenizer):
    def __call__(self, value, positions=False, chars=False, keeporiginal=False, removestops=True, start_pos=0, start_char=0, mode='', **kwargs):
        t = Token(positions, chars, removestops=removestops, mode=mode, **kwargs)
        seglist = jieba.cut(value, cut_all=False)
        pos = start_pos
        char_pos = start_char
        for w in seglist:
            w = w.strip()
            if not w:
                continue
            t.original = w
            t.text = w
            if positions:
                t.pos = pos
                pos += 1
            if chars:
                t.startchar = char_pos
                t.endchar = char_pos + len(w)
                char_pos += len(w)
            yield t


class JiebaAnalyzer(Analyzer):
    def __init__(self):
        self.tokenizer = JiebaTokenizer()

    def __call__(self, value, **kwargs):
        return self.tokenizer(value, **kwargs)


class BM25Searcher:

    def __init__(self, *, index_dir=None, id_field='id', content_field='content', analyzer: Analyzer = None):
        """
        BM25 Searcher
        :param index_dir: 索引文件目录
        :param id_field: 主键字段
        :param content_field: 内容字段
        :param analyzer: 分词器
        """
        self.index_dir = index_dir if index_dir else os.path.join(tempfile.gettempdir(), 'bm25_index')
        self.id_field = id_field
        self.content_field = content_field
        self.analyzer = analyzer if analyzer else JiebaAnalyzer()
        self.schema = Schema(
            **{self.id_field: ID(stored=True, unique=True), self.content_field: TEXT(stored=True, analyzer=self.analyzer)}
        )
        self._index = None
        self._index_lock = threading.Lock()

    def get_or_create_index(self):
        """
        获取或创建索引
        :return:
        """
        with self._index_lock:
            if self._index is not None:
                return self._index
            if not os.path.exists(self.index_dir):
                os.mkdir(self.index_dir)
            # 目录存在但无索引时也要 create_in
            if not exists_in(self.index_dir):
                self._index = create_in(self.index_dir, self.schema)
            else:
                self._index = open_dir(self.index_dir)
            return self._index

    def _build_index(self, docs):
        """
        构建查询索引
        :param docs: 文档
        """
        ix = self.get_or_create_index()
        writer = ix.writer()
        for doc in docs:
            writer.update_document(**{
                self.id_field: str(doc[self.id_field]),
                self.content_field: doc[self.content_field]
            })
        writer.commit()

    def search(self, query, *, top_k=20, group: type[GroupNode] = OrGroup, docs=None):
        """
        检索
        :param query: 查询语句
        :param top_k: 返回数量
        :param group: 关键词匹配关系
        :param docs: 可选的文档列表，如果提供则先构建索引再搜索；如果不提供则直接搜索现有索引
        :return: 命中文档的主键列表
        """
        if docs is not None:
            self._build_index(docs)
        ix = self.get_or_create_index()
        with ix.searcher() as searcher:
            parser = QueryParser(self.content_field, schema=ix.schema, group=group or OrGroup)
            q = parser.parse(query)
            results = searcher.search(q, limit=top_k)
            return [r[self.id_field] for r in results]
