#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : api_key_service.py
"""
import secrets
from dataclasses import dataclass
from uuid import UUID

from injector import inject
from sqlalchemy import desc

from internal.exception import ForbiddenException
from internal.model import Account, ApiKey
from internal.schema.api_key_schema import CreateApiKeyReq
from pkg.paginator import PaginatorReq, Paginator
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService


@inject
@dataclass
class ApiKeyService(BaseService):
    """API Key Service"""
    db: SQLAlchemy

    def create_api_key(self, req: CreateApiKeyReq, account: Account) -> ApiKey:
        """Create an API key based on the provided request data"""
        return self.create(
            ApiKey,
            account_id=account.id,
            api_key=self.generate_api_key(),
            is_active=req.is_active.data,
            remark=req.remark.data,
        )

    def get_api_key(self, api_key_id: UUID, account: Account) -> ApiKey:
        """Retrieve an API key record by ID and account"""
        api_key = self.get(ApiKey, api_key_id)
        if not api_key or api_key.account_id != account.id:
            raise ForbiddenException("API key does not exist or you do not have permission.")
        return api_key

    def get_api_by_by_credential(self, api_key: str) -> ApiKey:
        """Retrieve an API key record by its credential value"""
        return self.db.session.query(ApiKey).filter(
            ApiKey.api_key == api_key,
        ).one_or_none()

    def update_api_key(self, api_key_id: UUID, account: Account, **kwargs) -> ApiKey:
        """Update an API key using the provided fields"""
        api_key = self.get_api_key(api_key_id, account)
        self.update(api_key, **kwargs)
        return api_key

    def delete_api_key(self, api_key_id: UUID, account: Account) -> ApiKey:
        """Delete an API key by ID"""
        api_key = self.get_api_key(api_key_id, account)
        self.delete(api_key)
        return api_key

    def get_api_keys_with_page(self, req: PaginatorReq, account: Account) -> tuple[list[ApiKey], Paginator]:
        """Retrieve a paginated list of API keys for the given account"""
        # 1. Build paginator
        paginator = Paginator(db=self.db, req=req)

        # 2. Execute query with pagination
        api_keys = paginator.paginate(
            self.db.session.query(ApiKey).filter(
                ApiKey.account_id == account.id,
            ).order_by(desc("created_at"))
        )

        return api_keys, paginator

    @classmethod
    def generate_api_key(cls, api_key_prefix: str = "llmops-v1/") -> str:
        """Generate a random API key of length 48 with a prefix"""
        return api_key_prefix + secrets.token_urlsafe(48)
