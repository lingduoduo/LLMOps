#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : password.py
"""
import base64
import binascii
import hashlib
import re
from typing import Any

# Password validation regex: must include at least one letter, one number, and be 8–16 characters long
password_pattern = r"^(?=.*[a-zA-Z])(?=.*\d).{8,16}$"


def validate_password(password: str, pattern: str = password_pattern):
    """Check whether the given password meets the defined validation rules"""
    if re.match(pattern, password) is None:
        raise ValueError(
            "Password validation failed: it must contain at least one letter, one number, and be 8–16 characters long.")
    return


def hash_password(password: str, salt: Any) -> bytes:
    """Hash the given password together with the salt"""
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 10000)
    return binascii.hexlify(dk)


def compare_password(password: str, password_hashed_base64: Any, salt_base64: Any) -> bool:
    """Compare the provided password with the stored hash using the same salt"""
    return hash_password(password, base64.b64decode(salt_base64)) == base64.b64decode(password_hashed_base64)
