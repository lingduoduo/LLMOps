#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : base_service.py
"""
from typing import Any, Optional

from internal.exception import FailException
from pkg.sqlalchemy import SQLAlchemy


class BaseService:
    """Base service class providing simplified CRUD operations for database access"""
    db: SQLAlchemy

    def create(self, model: Any, **kwargs) -> Any:
        """Create a database record based on the given model and keyword arguments"""
        with self.db.auto_commit():
            model_instance = model(**kwargs)
            self.db.session.add(model_instance)
        return model_instance

    def delete(self, model_instance: Any) -> Any:
        """Delete a database record based on the given model instance"""
        with self.db.auto_commit():
            self.db.session.delete(model_instance)
        return model_instance

    def update(self, model_instance: Any, **kwargs) -> Any:
        """Update a database record based on the given model instance and fields"""
        with self.db.auto_commit():
            for field, value in kwargs.items():
                if hasattr(model_instance, field):
                    setattr(model_instance, field, value)
                else:
                    raise FailException("Failed to update: field does not exist")
        return model_instance

    def get(self, model: Any, primary_key: Any) -> Optional[Any]:
        """Retrieve a single record by primary key using the given model"""
        return self.db.session.query(model).get(primary_key)
