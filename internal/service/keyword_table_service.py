#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : keyword_table_service.py
"""
from dataclasses import dataclass
from uuid import UUID

from injector import inject
from redis import Redis

from internal.entity.cache_entity import (
    LOCK_KEYWORD_TABLE_UPDATE_KEYWORD_TABLE,
    LOCK_EXPIRE_TIME,
)
from internal.model import Segment, KeywordTable
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService


@inject
@dataclass
class KeywordTableService(BaseService):
    """Keyword table service for the knowledge base"""
    db: SQLAlchemy
    redis_client: Redis

    def get_keyword_table_from_dataset_id(self, dataset_id: UUID) -> KeywordTable:
        """Get the keyword table by the given dataset ID"""
        keyword_table = self.db.session.query(KeywordTable).filter(
            KeywordTable.dataset_id == dataset_id,
        ).one_or_none()
        if keyword_table is None:
            keyword_table = self.create(KeywordTable, dataset_id=dataset_id, keyword_table={})

        return keyword_table

    def delete_keyword_table_from_ids(self, dataset_id: UUID, segment_ids: list[UUID]) -> None:
        """Delete redundant entries from the keyword table using the dataset ID and a list of segment IDs"""
        # 1) Remove extra data in the dataset's keyword table. Lock this operation to avoid incorrect data under concurrency.
        cache_key = LOCK_KEYWORD_TABLE_UPDATE_KEYWORD_TABLE.format(dataset_id=dataset_id)
        with self.redis_client.lock(cache_key, timeout=LOCK_EXPIRE_TIME):
            # 2) Get the current dataset's keyword table
            keyword_table_record = self.get_keyword_table_from_dataset_id(dataset_id)
            keyword_table = keyword_table_record.keyword_table.copy()

            # 3) Convert the segment ID list to a set and create a set of keywords to delete empty keywords later
            segment_ids_to_delete = set([str(segment_id) for segment_id in segment_ids])
            keywords_to_delete = set()

            # 4) Iterate over all keywords to check and update
            for keyword, ids in keyword_table.items():
                ids_set = set(ids)
                if segment_ids_to_delete.intersection(ids_set):
                    keyword_table[keyword] = list(ids_set.difference(segment_ids_to_delete))
                    if not keyword_table[keyword]:
                        keywords_to_delete.add(keyword)

            # 5) Remove empty keyword entries (keywords that no longer map to any segment ID)
            for keyword in keywords_to_delete:
                del keyword_table[keyword]

            # 6) Persist updates back to the keyword table
            self.update(keyword_table_record, keyword_table=keyword_table)

    def add_keyword_table_from_ids(self, dataset_id: UUID, segment_ids: list[UUID]) -> None:
        """Add keywords to the keyword table for the given dataset ID and list of segment IDs"""
        # 1) Add entries to the dataset's keyword table. Lock this operation to avoid incorrect data under concurrency.
        cache_key = LOCK_KEYWORD_TABLE_UPDATE_KEYWORD_TABLE.format(dataset_id=dataset_id)
        with self.redis_client.lock(cache_key, timeout=LOCK_EXPIRE_TIME):
            # 2) Get the specified dataset's keyword table
            keyword_table_record = self.get_keyword_table_from_dataset_id(dataset_id)
            keyword_table = {
                field: set(value) for field, value in keyword_table_record.keyword_table.items()
            }

            # 3) Query segments to get their keywords based on segment_ids
            segments = self.db.session.query(Segment).with_entities(Segment.id, Segment.keywords).filter(
                Segment.id.in_(segment_ids),
            ).all()

            # 4) Add new keywords to the keyword table
            for id, keywords in segments:
                for keyword in keywords:
                    if keyword not in keyword_table:
                        keyword_table[keyword] = set()
                    keyword_table[keyword].add(str(id))

            # 5) Update the keyword table
            self.update(
                keyword_table_record,
                keyword_table={field: list(value) for field, value in keyword_table.items()}
            )
