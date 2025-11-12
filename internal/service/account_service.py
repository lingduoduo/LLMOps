#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : account_service.py
"""
import base64
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from flask import request
from injector import inject

from internal.exception import FailException
from internal.model import Account, AccountOAuth
from pkg.password import hash_password, compare_password
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService
from .jwt_service import JwtService


@inject
@dataclass
class AccountService(BaseService):
    """Account Service"""
    db: SQLAlchemy
    jwt_service: JwtService

    def get_account(self, account_id: UUID) -> Account:
        """Retrieve an account by its ID"""
        return self.get(Account, account_id)

    def get_account_oauth_by_provider_name_and_openid(
            self,
            provider_name: str,
            openid: str,
    ) -> AccountOAuth:
        """Retrieve third-party OAuth record by provider name and openid"""
        return self.db.session.query(AccountOAuth).filter(
            AccountOAuth.provider == provider_name,
            AccountOAuth.openid == openid,
        ).one_or_none()

    def get_account_by_email(self, email: str) -> Account:
        """Retrieve account information by email"""
        return self.db.session.query(Account).filter(
            Account.email == email,
        ).one_or_none()

    def create_account(self, **kwargs) -> Account:
        """Create a new account using provided keyword arguments"""
        return self.create(Account, **kwargs)

    def update_password(self, password: str, account: Account) -> Account:
        """Update an account's password"""
        # 1. Generate a random salt for the password
        salt = secrets.token_bytes(16)
        base64_salt = base64.b64encode(salt).decode()

        # 2. Hash the password using the generated salt
        password_hashed = hash_password(password, salt)
        base64_password_hashed = base64.b64encode(password_hashed).decode()

        # 3. Update the account record with new password and salt
        self.update_account(account, password=base64_password_hashed, password_salt=base64_salt)

        return account

    def update_account(self, account: Account, **kwargs) -> Account:
        """Update account fields with provided data"""
        self.update(account, **kwargs)
        return account

    def password_login(self, email: str, password: str) -> dict[str, Any]:
        """Authenticate an account using email and password"""
        # 1. Check if the account exists
        account = self.get_account_by_email(email)
        if not account:
            raise FailException("Account does not exist or password is incorrect. Please verify and try again.")

        # 2. Verify the provided password
        if not account.is_password_set or not compare_password(
                password,
                account.password,
                account.password_salt,
        ):
            raise FailException("Account does not exist or password is incorrect. Please verify and try again.")

        # 3. Generate an access token with expiration
        expire_at = int((datetime.now() + timedelta(days=30)).timestamp())
        payload = {
            "sub": str(account.id),
            "iss": "llmops",
            "exp": expire_at,
        }
        access_token = self.jwt_service.generate_token(payload)

        # 4. Update login metadata
        self.update(
            account,
            last_login_at=datetime.now(),
            last_login_ip=request.remote_addr,
        )

        return {
            "expire_at": expire_at,
            "access_token": access_token,
        }
