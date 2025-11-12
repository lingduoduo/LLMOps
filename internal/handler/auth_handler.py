#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : auth_handler.py
"""
from dataclasses import dataclass

from flask_login import logout_user, login_required
from injector import inject

from internal.schema.auth_schema import PasswordLoginReq, PasswordLoginResp
from internal.service import AccountService
from pkg.response import success_message, validate_error_json, success_json


@inject
@dataclass
class AuthHandler:
    """LLMOps platform's built-in authentication and authorization handler"""
    account_service: AccountService

    def password_login(self):
        """Login with account and password"""
        # 1. Extract and validate the request data
        req = PasswordLoginReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Call the service layer to authenticate the account
        credential = self.account_service.password_login(req.email.data, req.password.data)

        # 3. Build the response structure and return
        resp = PasswordLoginResp()
        return success_json(resp.dump(credential))

    @login_required
    def logout(self):
        """Log out; used to notify the frontend to clear authentication credentials"""
        logout_user()
        return success_message("Logout successful")
