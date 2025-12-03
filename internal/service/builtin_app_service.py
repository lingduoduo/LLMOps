#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : builtin_app_service.py
"""
from dataclasses import dataclass

from injector import inject

from internal.core.builtin_apps import BuiltinAppManager
from internal.core.builtin_apps.entities.builtin_app_entity import BuiltinAppEntity
from internal.core.builtin_apps.entities.category_entity import CategoryEntity
from internal.entity.app_entity import AppConfigType
from internal.entity.app_entity import AppStatus
from internal.exception import NotFoundException
from internal.model import Account, App, AppConfigVersion
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService


@inject
@dataclass
class BuiltinAppService(BaseService):
    """Builtin application service"""
    db: SQLAlchemy
    builtin_app_manager: BuiltinAppManager

    def get_categories(self) -> list[CategoryEntity]:
        """Retrieve builtin app category list"""
        return self.builtin_app_manager.get_categories()

    def get_builtin_apps(self) -> list[BuiltinAppEntity]:
        """Retrieve all builtin app entities"""
        return self.builtin_app_manager.get_builtin_apps()

    def add_builtin_app_to_space(self, builtin_app_id: str, account: Account) -> App:
        """Add the specified builtin app to the user's personal workspace"""
        # 1. Get builtin app info and check if it exists
        builtin_app = self.builtin_app_manager.get_builtin_app(builtin_app_id)
        if not builtin_app:
            raise NotFoundException("The builtin app does not exist. Please verify and retry.")

        # 2. Start an auto-commit transaction context
        with self.db.auto_commit():
            # 3. Create the App record
            app = App(
                account_id=account.id,
                status=AppStatus.DRAFT,
                **builtin_app.model_dump(include={"name", "icon", "description"})
            )
            self.db.session.add(app)
            self.db.session.flush()

            # 4. Create the draft app config record
            draft_app_config = AppConfigVersion(
                app_id=app.id,
                model_config=builtin_app.language_model_config,
                config_type=AppConfigType.DRAFT,
                **builtin_app.model_dump(include={
                    "dialog_round",
                    "preset_prompt",
                    "tools",
                    "retrieval_config",
                    "long_term_memory",
                    "opening_statement",
                    "opening_questions",
                    "speech_to_text",
                    "text_to_speech",
                    "review_config",
                    "suggested_after_answer",
                })
            )
            self.db.session.add(draft_app_config)
            self.db.session.flush()

            # 5. Update App with the created draft config ID
            app.draft_app_config_id = draft_app_config.id

        return app
