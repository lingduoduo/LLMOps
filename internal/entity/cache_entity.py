#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : cache_entity.py
"""
# Cache lock expiration time in seconds (default: 600)
LOCK_EXPIRE_TIME = 600

# Cache lock for updating a document's enabled status
LOCK_DOCUMENT_UPDATE_ENABLED = "lock:document:update:enabled_{document_id}"

# Cache lock for updating the keyword table
LOCK_KEYWORD_TABLE_UPDATE_KEYWORD_TABLE = "lock:keyword_table:update:keyword_table_{dataset_id}"

# Cache lock for updating a segment's enabled status
LOCK_SEGMENT_UPDATE_ENABLED = "lock:segment:update:enabled_{segment_id}"
