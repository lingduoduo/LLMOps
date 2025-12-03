#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : builtin_app_handler.py
"""
from dataclasses import dataclass

from flask_login import login_required, current_user
from injector import inject
from internal.schema.builtin_app_schema import (
    GetBuiltinAppCategoriesResp,
    GetBuiltinAppsResp,
    AddBuiltinAppToSpaceReq,
)

from internal.service import BuiltinAppService
from pkg.response import success_json, validate_error_json


@inject
@dataclass
class BuiltinAppHandler:
    """LLMOps built-in app handler"""
    builtin_app_service: BuiltinAppService

    @login_required
    def get_builtin_app_categories(self):
        """Get the list of built-in app categories"""
        categories = self.builtin_app_service.get_categories()
        resp = GetBuiltinAppCategoriesResp(many=True)
        return success_json(resp.dump(categories))

    @login_required
    def get_builtin_apps(self):
        """Get the list of all built-in apps"""
        builtin_apps = self.builtin_app_service.get_builtin_apps()
        resp = GetBuiltinAppsResp(many=True)
        return success_json(resp.dump(builtin_apps))

    @login_required
    def add_builtin_app_to_space(self):
        """Add the specified built-in app to the user's space"""
        # 1. Extract request and validate
        req = AddBuiltinAppToSpaceReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Add the specified built-in app template to the user's space
        app = self.builtin_app_service.add_builtin_app_to_space(req.builtin_app_id.data, current_user)

        return success_json({"id": app.id})
