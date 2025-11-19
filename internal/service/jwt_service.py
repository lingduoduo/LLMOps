#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : jwt_service.py
"""
import os
from dataclasses import dataclass
from typing import Any

import jwt
from injector import inject

from internal.exception import UnauthorizedException


@inject
@dataclass
class JwtService:
    """JWT Service"""

    @classmethod
    def generate_token(cls, payload: dict[str, Any]) -> str:
        """Generate a JWT token based on the provided payload"""
        secret_key = os.getenv("JWT_SECRET_KEY")
        return jwt.encode(payload, secret_key, algorithm="HS256")

    @classmethod
    def parse_token(cls, token: str) -> dict[str, Any]:
        """Decode the provided JWT token and return the payload"""
        secret_key = os.getenv("JWT_SECRET_KEY")
        try:
            return jwt.decode(token, secret_key, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            raise UnauthorizedException("Authorization token has expired. Please log in again.")
        except jwt.InvalidTokenError:
            raise UnauthorizedException("Invalid token. Please log in again.")
        except Exception as e:
            raise UnauthorizedException(str(e))
