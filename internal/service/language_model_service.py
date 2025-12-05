#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : language_model_service.py
"""
import mimetypes
import os
from dataclasses import dataclass
from typing import Any

from flask import current_app
from injector import inject

from internal.core.language_model import LanguageModelManager
from internal.exception import NotFoundException
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService


@inject
@dataclass
class LanguageModelService(BaseService):
    """Language model service"""
    db: SQLAlchemy
    language_model_manager: LanguageModelManager

    def get_language_models(self) -> list[dict[str, Any]]:
        """Retrieve all model lists configured in the LLMOps project"""
        # 1. Call the language model manager to get all providers
        providers = self.language_model_manager.get_providers()

        # 2. Build the language model list
        language_models = []
        for provider in providers:
            # 3. Retrieve provider metadata and model entities
            provider_entity = provider.provider_entity
            model_entities = provider.get_model_entities()

            # 4. Construct response dictionary
            language_model = {
                "name": provider_entity.name,
                "position": provider.position,
                "label": provider_entity.label,
                "icon": provider_entity.icon,
                "description": provider_entity.description,
                "background": provider_entity.background,
                "support_model_types": provider_entity.supported_model_types,
                "models": [{
                    "model": model_entity.model_name,
                    "label": model_entity.label,
                    "model_type": model_entity.model_type,
                    "context_window": model_entity.context_window,
                    "max_output_tokens": model_entity.max_output_tokens,
                    "features": model_entity.features,
                    "attributes": model_entity.attributes,
                    "metadata": model_entity.metadata,
                    "parameters": [{
                        "name": parameter.name,
                        "label": parameter.label,
                        "type": parameter.type.value,
                        "help": parameter.help,
                        "required": parameter.required,
                        "default": parameter.default,
                        "min": parameter.min,
                        "max": parameter.max,
                        "precision": parameter.precision,
                        "options": [{"label": option.label, "value": option.value} for option in parameter.options],
                    } for parameter in model_entity.parameters],
                } for model_entity in model_entities]
            }
            language_models.append(language_model)

        return language_models

    def get_language_model(self, provider_name: str, model_name: str) -> dict[str, Any]:
        """Retrieve detailed model information based on provider name + model name"""
        # 1. Get provider and model entity
        provider = self.language_model_manager.get_provider(provider_name)
        if not provider:
            raise NotFoundException("The provider does not exist")

        # 2. Get model entity
        model_entity = provider.get_model_entity(model_name)
        if not model_entity:
            raise NotFoundException("The model does not exist")

        # 3. Build response
        language_model = {
            "model": model_entity.model_name,
            "label": model_entity.label,
            "model_type": model_entity.model_type,
            "context_window": model_entity.context_window,
            "max_output_tokens": model_entity.max_output_tokens,
            "features": model_entity.features,
            "attributes": model_entity.attributes,
            "metadata": model_entity.metadata,
            "parameters": [{
                "name": parameter.name,
                "label": parameter.label,
                "type": parameter.type.value,
                "help": parameter.help,
                "required": parameter.required,
                "default": parameter.default,
                "min": parameter.min,
                "max": parameter.max,
                "precision": parameter.precision,
                "options": [{"label": option.label, "value": option.value} for option in parameter.options],
            } for parameter in model_entity.parameters],
        }

        return language_model

    def get_language_model_icon(self, provider_name: str) -> tuple[bytes, str]:
        """Retrieve the icon associated with a provider by provider name"""
        # 1. Get provider information
        provider = self.language_model_manager.get_provider(provider_name)
        if not provider:
            raise NotFoundException("The provider does not exist")

        # 2. Get project root path
        root_path = os.path.dirname(os.path.dirname(current_app.root_path))

        # 3. Build provider folder path
        provider_path = os.path.join(
            root_path,
            "internal", "core", "language_model", "providers", provider_name,
        )

        # 4. Build the icon file path
        icon_path = os.path.join(provider_path, "_asset", provider.provider_entity.icon)

        # 5. Check whether the icon exists
        if not os.path.exists(icon_path):
            raise NotFoundException("The provider did not supply an icon under _asset")

        # 6. Determine icon MIME type
        mimetype, _ = mimetypes.guess_type(icon_path)
        mimetype = mimetype or "application/octet-stream"

        # 7. Read and return icon bytes
        with open(icon_path, "rb") as f:
            byte_data = f.read()
            return byte_data, mimetype
