#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : full_text_retriever.py
"""
from collections import Counter
from typing import List
from uuid import UUID

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document as LCDocument
from langchain_core.pydantic_v1 import Field
from langchain_core.retrievers import BaseRetriever

from internal.model import KeywordTable, Segment
from internal.service import JiebaService
from pkg.sqlalchemy import SQLAlchemy


class FullTextRetriever(BaseRetriever):
    """Full-text retriever"""
    db: SQLAlchemy
    dataset_ids: list[UUID]
    jieba_service: JiebaService
    search_kwargs: dict = Field(default_factory=dict)

    def _get_relevant_documents(
            self, query: str, *, run_manager: CallbackManagerForRetrieverRun,
    ) -> List[LCDocument]:
        """Run keyword-based retrieval for the given query and return LangChain Documents"""
        # 1) Convert the query into a list of keywords
        keywords = self.jieba_service.extract_keywords(query, 10)

        # 2) Fetch keyword tables for the specified datasets
        keyword_tables = [
            keyword_table for keyword_table, in
            self.db.session.query(KeywordTable).with_entities(KeywordTable.keyword_table).filter(
                KeywordTable.dataset_id.in_(self.dataset_ids)
            ).all()
        ]

        # 3) Traverse all keyword tables and find segment IDs matching the query keywords
        all_ids = []
        for keyword_table in keyword_tables:
            # 4) Iterate over each entry in a keyword table
            for keyword, segment_ids in keyword_table.items():
                # 5) If the keyword appears in our query keywords, collect its segment IDs
                if keyword in keywords:
                    all_ids.extend(segment_ids)

        # 6) Count how frequently each segment_id appears
        id_counter = Counter(all_ids)

        # 7) Take the top-k by frequency: [(segment_id, freq), ...]
        k = self.search_kwargs.get("k", 4)
        top_k_ids = id_counter.most_common(k)

        # 8) Look up the corresponding Segment rows from the database
        segments = self.db.session.query(Segment).filter(
            Segment.id.in_([id for id, _ in top_k_ids])
        ).all()
        segment_dict = {str(segment.id): segment for segment in segments}

        # 9) Sort segments by frequency order
        sorted_segments = [segment_dict[str(id)] for id, freq in top_k_ids if id in segment_dict]

        # 10) Build LangChain Documents
        lc_documents = [
            LCDocument(
                page_content=segment.content,
                metadata={
                    "account_id": str(segment.account_id),
                    "dataset_id": str(segment.dataset_id),
                    "document_id": str(segment.document_id),
                    "segment_id": str(segment.id),
                    "node_id": str(segment.node_id),
                    "document_enabled": True,
                    "segment_enabled": True,
                    "score": 0,
                },
            )
            for segment in sorted_segments
        ]

        return lc_documents
