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
from langchain_openai import ChatOpenAI

from internal.core.language_model import LanguageModelManager
from internal.core.language_model.entities.model_entity import BaseLanguageModel
from internal.exception import NotFoundException
from internal.lib.helper import convert_model_to_dict
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService


@inject
@dataclass
class LanguageModelService(BaseService):
    """Language model service"""
    db: SQLAlchemy
    language_model_manager: LanguageModelManager

    def get_language_models(self) -> list[dict[str, Any]]:
        """Retrieve all model configurations defined in the LLMOps project"""
        # 1. Retrieve provider list from the language model manager
        providers = self.language_model_manager.get_providers()

        # 2. Build the language model response list
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
                "models": convert_model_to_dict(model_entities),
            }
            language_models.append(language_model)

        return language_models

    def get_language_model(self, provider_name: str, model_name: str) -> dict[str, Any]:
        """Retrieve detailed model information using provider name + model name"""
        # 1. Retrieve provider + model entity
        provider = self.language_model_manager.get_provider(provider_name)
        if not provider:
            raise NotFoundException("The provider does not exist")

        # 2. Retrieve the model entity
        model_entity = provider.get_model_entity(model_name)
        if not model_entity:
            raise NotFoundException("The model does not exist")

        return convert_model_to_dict(model_entity)

    def get_language_model_icon(self, provider_name: str) -> tuple[bytes, str]:
        """Retrieve the icon associated with a provider by name"""
        # 1. Retrieve provider metadata
        provider = self.language_model_manager.get_provider(provider_name)
        if not provider:
            raise NotFoundException("The provider does not exist")

        # 2. Get the root project path
        root_path = os.path.dirname(os.path.dirname(current_app.root_path))

        # 3. Build the provider folder path
        provider_path = os.path.join(
            root_path,
            "internal", "core", "language_model", "providers", provider_name,
        )

        # 4. Build the icon file path
        icon_path = os.path.join(provider_path, "_asset", provider.provider_entity.icon)

        # 5. Ensure the icon exists
        if not os.path.exists(icon_path):
            raise NotFoundException("No icon found under the provider's _asset folder")

        # 6. Determine MIME type
        mimetype, _ = mimetypes.guess_type(icon_path)
        mimetype = mimetype or "application/octet-stream"

        # 7. Read and return icon bytes
        with open(icon_path, "rb") as f:
            byte_data = f.read()
            return byte_data, mimetype

    def load_language_model(self, model_config: dict[str, Any]) -> BaseLanguageModel:
        """Load a language model instance based on the given configuration"""
        try:
            # 1. Extract provider, model, and parameters from model_config
            provider_name = model_config.get("provider", "")
            model_name = model_config.get("model", "")
            parameters = model_config.get("parameters", {})

            # 2. Retrieve provider, model entity, and model class from manager
            provider = self.language_model_manager.get_provider(provider_name)
            model_entity = provider.get_model_entity(model_name)
            model_class = provider.get_model_class(model_entity.model_type)

            # 3. Instantiate and return the model
            return model_class(
                **model_entity.attributes,
                **parameters,
                features=model_entity.features,
                metadata=model_entity.metadata,
            )
        except Exception:
            return self.load_default_language_model()

    @classmethod
    def load_default_language_model(cls) -> BaseLanguageModel:
        """Load a fallback default language model when errors occur or no model is found"""
        return ChatOpenAI(model="gpt-4o-mini", temperature=1, max_tokens=8192)
