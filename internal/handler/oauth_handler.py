#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : oauth_handler.py
"""
from dataclasses import dataclass

from injector import inject
from internal.schema.oauth_schema import AuthorizeReq, AuthorizeResp

from internal.service import OAuthService
from pkg.response import success_json, validate_error_json


@inject
@dataclass
class OAuthHandler:
    """Third-party OAuth authentication handler."""
    oauth_service: OAuthService

    def provider(self, provider_name: str):
        """Get the authorization redirect URL based on the given provider name."""
        # 1. Retrieve the OAuth provider instance by provider name
        oauth = self.oauth_service.get_oauth_by_provider_name(provider_name)

        # 2. Generate the authorization redirect URL
        redirect_url = oauth.get_authorization_url()

        return success_json({"redirect_url": redirect_url})

    def authorize(self, provider_name: str):
        """Obtain third-party authorization information based on provider name and code."""
        # 1. Extract and validate request data
        req = AuthorizeReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Log in using OAuth service
        credential = self.oauth_service.oauth_login(provider_name, req.code.data)

        return success_json(AuthorizeResp().dump(credential))
