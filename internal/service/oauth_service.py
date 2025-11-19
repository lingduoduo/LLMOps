#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : oauth_service.py
"""
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from flask import request
from injector import inject

from internal.exception import NotFoundException
from internal.model import AccountOAuth
from pkg.oauth import OAuth, GithubOAuth
from pkg.sqlalchemy import SQLAlchemy
from .account_service import AccountService
from .base_service import BaseService
from .jwt_service import JwtService


@inject
@dataclass
class OAuthService(BaseService):
    """Third-party OAuth authentication service."""
    db: SQLAlchemy
    jwt_service: JwtService
    account_service: AccountService

    @classmethod
    def get_all_oauth(cls) -> dict[str, OAuth]:
        """Retrieve all third-party OAuth integrations supported by LLMOps."""
        # 1. Instantiate supported OAuth providers
        github = GithubOAuth(
            client_id=os.getenv("GITHUB_CLIENT_ID"),
            client_secret=os.getenv("GITHUB_CLIENT_SECRET"),
            redirect_uri=os.getenv("GITHUB_REDIRECT_URI"),
        )

        # 2. Construct and return a dictionary of providers
        return {
            "github": github,
        }

    @classmethod
    def get_oauth_by_provider_name(cls, provider_name: str) -> OAuth:
        """Retrieve an OAuth service by its provider name."""
        all_oauth = cls.get_all_oauth()
        oauth = all_oauth.get(provider_name)

        if oauth is None:
            raise NotFoundException(f"The OAuth provider [{provider_name}] does not exist.")

        return oauth

    def oauth_login(self, provider_name: str, code: str) -> dict[str, Any]:
        """Perform third-party OAuth login and return access credentials and expiration time."""
        # 1. Retrieve the OAuth provider instance
        oauth = self.get_oauth_by_provider_name(provider_name)

        # 2. Obtain access token from the provider using the authorization code
        oauth_access_token = oauth.get_access_token(code)

        # 3. Retrieve user information using the access token
        oauth_user_info = oauth.get_user_info(oauth_access_token)

        # 4. Retrieve existing OAuth record using provider name and openid
        account_oauth = self.account_service.get_account_oauth_by_provider_name_and_openid(
            provider_name,
            oauth_user_info.id,
        )
        if not account_oauth:
            # 5. If this is the user's first login, check if an account with the same email exists
            account = self.account_service.get_account_by_email(oauth_user_info.email)
            if not account:
                # 6. Account does not exist; register a new account
                account = self.account_service.create_account(
                    name=oauth_user_info.name,
                    email=oauth_user_info.email,
                )
            # 7. Create a new OAuth authorization record
            account_oauth = self.create(
                AccountOAuth,
                account_id=account.id,
                provider=provider_name,
                openid=oauth_user_info.id,
                encrypted_token=oauth_access_token,
            )
        else:
            # 8. Retrieve existing account information
            account = self.account_service.get_account(account_oauth.account_id)

        # 9. Update account information (last login time and IP address)
        self.update(
            account,
            last_login_at=datetime.now(),
            last_login_ip=request.remote_addr,
        )
        self.update(
            account_oauth,
            encrypted_token=oauth_access_token,
        )

        # 10. Generate access credential with expiration
        expire_at = int((datetime.now() + timedelta(days=30)).timestamp())
        payload = {
            "sub": str(account.id),
            "iss": "llmops",
            "exp": expire_at,
        }
        access_token = self.jwt_service.generate_token(payload)

        return {
            "expire_at": expire_at,
            "access_token": access_token,
        }
