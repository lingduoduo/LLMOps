#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : middleware.py
"""
from dataclasses import dataclass
from typing import Optional

from flask import Request
from injector import inject

from internal.exception import UnauthorizedException
from internal.model import Account
from internal.service import JwtService, AccountService, ApiKeyService


@inject
@dataclass
class Middleware:
    """Application middleware. You can override request_loader and unauthorized_handler."""
    jwt_service: JwtService
    api_key_service: ApiKeyService
    account_service: AccountService

    def request_loader(self, request: Request) -> Optional[Account]:
        """Request loader for the login manager."""
        # 1. Create a dedicated request loader for the `llmops` blueprint
        if request.blueprint == "llmops":
            # 2. Validate and get the access_token
            access_token = self._validate_credential(request)

            # 3. Parse the token payload to get user info and return the account
            payload = self.jwt_service.parse_token(access_token)
            account_id = payload.get("sub")
            return self.account_service.get_account(account_id)

        elif request.blueprint == "openapi":
            # 4. Validate and get the api_key
            api_key = self._validate_credential(request)

            # 5. Parse and fetch the API key record
            api_key_record = self.api_key_service.get_api_by_by_credential(api_key)

            # 6. Check whether the API key record exists and is active; otherwise raise an error
            if not api_key_record or not api_key_record.is_active:
                raise UnauthorizedException("API key does not exist or is not active")

            # 7. Return the account associated with the API key
            return api_key_record.account
        else:
            return None

    @classmethod
    def _validate_credential(cls, request: Request) -> str:
        """Validate the credential in the request headers (covers both access_token and api_key)."""
        # 1. Extract the Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            raise UnauthorizedException(
                "Authorization is required to access this endpoint. Please log in and try again.")

        # 2. If there is no whitespace separator, validation fails.
        #    Expected format: Authorization: Bearer <access_token>
        if " " not in auth_header:
            raise UnauthorizedException(
                "Authorization is required to access this endpoint. Invalid authorization format.")

        # 4. Split the authorization header; it must follow the 'Bearer <credential>' format
        auth_schema, credential = auth_header.split(None, 1)
        if auth_schema.lower() != "bearer":
            raise UnauthorizedException(
                "Authorization is required to access this endpoint. Invalid authorization scheme.")

        return credential
