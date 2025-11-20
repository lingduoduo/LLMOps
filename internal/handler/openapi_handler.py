#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : openapi_handler.py
"""
from dataclasses import dataclass

from flask_login import login_required, current_user
from injector import inject
from internal.schema.openapi_schema import OpenAPIChatReq

from internal.service import OpenAPIService
from pkg.response import validate_error_json, compact_generate_response


@inject
@dataclass
class OpenAPIHandler:
    """OpenAPI Request Handler"""
    openapi_service: OpenAPIService

    @login_required
    def chat(self):
        """Open Chat API endpoint"""
        # 1. Extract and validate request data
        req = OpenAPIChatReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Call service to create chat response
        resp = self.openapi_service.chat(req, current_user)

        return compact_generate_response(resp)
