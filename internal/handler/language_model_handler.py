#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : language_model_handler.py
"""
import io
from dataclasses import dataclass

from flask import send_file
from flask_login import login_required
from injector import inject

from internal.service import LanguageModelService
from pkg.response import success_json


@inject
@dataclass
class LanguageModelHandler:
    """Language model request handler"""
    language_model_service: LanguageModelService

    @login_required
    def get_language_models(self):
        """Retrieve all language model providers"""
        return success_json(self.language_model_service.get_language_models())

    @login_required
    def get_language_model(self, provider_name: str, model_name: str):
        """Retrieve model details by provider name + model name"""
        return success_json(self.language_model_service.get_language_model(provider_name, model_name))

    def get_language_model_icon(self, provider_name: str):
        """Retrieve the icon file for a provider based on its name"""
        icon, mimetype = self.language_model_service.get_language_model_icon(provider_name)
        return send_file(io.BytesIO(icon), mimetype)
