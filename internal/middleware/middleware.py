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
from internal.service import JwtService, AccountService


@inject
@dataclass
class Middleware:
    """Application middleware.
    You can override `request_loader` and `unauthorized_handler` for custom authentication logic.
    """
    jwt_service: JwtService
    account_service: AccountService

    def request_loader(self, request: Request) -> Optional[Account]:
        """Request loader for login management"""
        # 1. Handle authentication only for the `llmops` route blueprint
        if request.blueprint == "llmops":
            # 2. Extract Authorization header from the request
            auth_header = request.headers.get("Authorization")
            if not auth_header:
                raise UnauthorizedException("This endpoint requires authorization. Please log in and try again.")

            # 3. Validate Authorization header format: must contain a space
            # Expected format: Authorization: Bearer <access_token>
            if " " not in auth_header:
                raise UnauthorizedException("Authorization failed: malformed Authorization header.")

            # 4. Split and validate schema
            auth_schema, access_token = auth_header.split(None, 1)
            if auth_schema.lower() != "bearer":
                raise UnauthorizedException("Authorization failed: invalid authentication schema.")

            # 5. Decode token and retrieve the corresponding account
            payload = self.jwt_service.parse_token(access_token)
            account_id = payload.get("sub")
            return self.account_service.get_account(account_id)
        else:
            return None
