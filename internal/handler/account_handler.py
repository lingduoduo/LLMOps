#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : account_handler.py
"""
from dataclasses import dataclass

from flask_login import login_required, current_user
from injector import inject
from internal.schema.account_schema import GetCurrentUserResp, UpdatePasswordReq, UpdateNameReq, UpdateAvatarReq

from internal.service import AccountService
from pkg.response import success_json, validate_error_json, success_message


@inject
@dataclass
class AccountHandler:
    """Account settings handler"""
    account_service: AccountService

    @login_required
    def get_current_user(self):
        """Retrieve information of the currently logged-in user"""
        resp = GetCurrentUserResp()
        return success_json(resp.dump(current_user))

    @login_required
    def update_password(self):
        """Update the password of the currently logged-in user"""
        # 1. Extract and validate request data
        req = UpdatePasswordReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Call the service layer to update the account password
        self.account_service.update_password(req.password.data, current_user)

        return success_message("Password updated successfully")

    @login_required
    def update_name(self):
        """Update the display name of the currently logged-in user"""
        # 1. Extract and validate request data
        req = UpdateNameReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Call the service layer to update the account name
        self.account_service.update_account(current_user, name=req.name.data)

        return success_message("Name updated successfully")

    @login_required
    def update_avatar(self):
        """Update the avatar of the currently logged-in user"""
        # 1. Extract and validate request data
        req = UpdateAvatarReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Call the service layer to update the account avatar
        self.account_service.update_account(current_user, avatar=req.avatar.data)

        return success_message("Avatar updated successfully")
