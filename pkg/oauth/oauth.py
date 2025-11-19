#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : oauth.py
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class OAuthUserInfo:
    """Basic user information obtained through OAuth; only stores id, name, and email."""
    id: str
    name: str
    email: str


@dataclass
class OAuth(ABC):
    """Base class for third-party OAuth authentication."""
    client_id: str  # Client ID
    client_secret: str  # Client secret
    redirect_uri: str  # Redirect URI

    @abstractmethod
    def get_provider(self) -> str:
        """Return the name of the service provider."""
        pass

    @abstractmethod
    def get_authorization_url(self) -> str:
        """Return the URL for redirecting users to the authorization page."""
        pass

    @abstractmethod
    def get_access_token(self, code: str) -> str:
        """Obtain an access token using the provided authorization code."""
        pass

    @abstractmethod
    def get_raw_user_info(self, token: str) -> dict:
        """Retrieve raw user information from the provider using the access token."""
        pass

    def get_user_info(self, token: str) -> OAuthUserInfo:
        """Retrieve the standardized OAuthUserInfo object using the access token."""
        raw_info = self.get_raw_user_info(token)
        return self._transform_user_info(raw_info)

    @abstractmethod
    def _transform_user_info(self, raw_info: dict) -> OAuthUserInfo:
        """Convert the raw OAuth user information into a standardized OAuthUserInfo object."""
        pass
