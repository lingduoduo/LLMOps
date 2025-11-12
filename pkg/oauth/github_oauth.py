#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : github_oauth.py
"""
import urllib.parse

import requests

from .oauth import OAuth, OAuthUserInfo


class GithubOAuth(OAuth):
    """GitHub OAuth third-party authentication class"""
    _AUTHORIZE_URL = "https://github.com/login/oauth/authorize"  # Authorization redirect endpoint
    _ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"  # Access token endpoint
    _USER_INFO_URL = "https://api.github.com/user"  # User info endpoint
    _EMAIL_INFO_URL = "https://api.github.com/user/emails"  # User email endpoint

    def get_provider(self) -> str:
        return "github"

    def get_authorization_url(self) -> str:
        """Generate GitHub authorization URL"""
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": "user:email",  # Request only basic user info
        }
        return f"{self._AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"

    def get_access_token(self, code: str) -> str:
        """Exchange the authorization code for an access token"""
        # 1. Build request payload
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": self.redirect_uri,
        }
        headers = {"Accept": "application/json"}

        # 2. Send POST request to get access token
        resp = requests.post(self._ACCESS_TOKEN_URL, data=data, headers=headers)
        resp.raise_for_status()
        resp_json = resp.json()

        # 3. Extract access_token from response
        access_token = resp_json.get("access_token")
        if not access_token:
            raise ValueError(f"GitHub OAuth authorization failed: {resp_json}")

        return access_token

    def get_raw_user_info(self, token: str) -> dict:
        """Retrieve the raw user info and email from GitHub API"""
        # 1. Set request header
        headers = {"Authorization": f"token {token}"}

        # 2. Get user profile info
        resp = requests.get(self._USER_INFO_URL, headers=headers)
        resp.raise_for_status()
        raw_info = resp.json()

        # 3. Get user email info
        email_resp = requests.get(self._EMAIL_INFO_URL, headers=headers)
        email_resp.raise_for_status()
        email_info = email_resp.json()

        # 4. Extract primary email
        primary_email = next((email for email in email_info if email.get("primary", None)), None)

        return {**raw_info, "email": primary_email.get("email", None)}

    def _transform_user_info(self, raw_info: dict) -> OAuthUserInfo:
        """Convert raw GitHub user info into standardized OAuthUserInfo object"""
        # 1. Extract email; if not available, set a default
        email = raw_info.get("email")
        if not email:
            email = f"{raw_info.get('id')}+{raw_info.get('login')}@user.no-reply.github.com"

        # 2. Construct standardized user info
        return OAuthUserInfo(
            id=str(raw_info.get("id")),
            name=str(raw_info.get("name")),
            email=str(email),
        )
