#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : http.py
"""
import logging
import os

from flask import Flask
from flask_cors import CORS
from flask_migrate import Migrate

from config import Config
from internal.exception import CustomException
from internal.extension import logging_extension
from internal.router import Router
from pkg.response import json, Response, HttpCode
from pkg.sqlalchemy import SQLAlchemy


class Http(Flask):
    """HTTP service engine"""

    def __init__(
            self,
            *args,
            conf: Config,
            db: SQLAlchemy,
            migrate: Migrate,
            router: Router,
            **kwargs,
    ):
        # 1) Call parent constructor to initialize
        super().__init__(*args, **kwargs)

        # 2) Initialize application config
        self.config.from_object(conf)

        # 3) Register a global error handler
        self.register_error_handler(Exception, self._register_error_handler)

        # 4) Initialize Flask extensions
        db.init_app(self)
        migrate.init_app(self, db, directory="internal/migration")
        # redis_extension.init_app(self)
        # celery_extension.init_app(self)
        logging_extension.init_app(self)

        # 5) Enable CORS between frontend and backend
        CORS(self, resources={
            r"/*": {
                "origins": "*",
                "supports_credentials": True,
                # "methods": ["GET", "POST"],
                # "allow_headers": ["Content-Type"],
            }
        })

        # 6) Register application routes
        router.register_router(self)

    def _register_error_handler(self, error: Exception):
        # 1) Log the exception details
        logging.error("An error occurred: %s", error, exc_info=True)

        # 2) If it's our custom exception, return its message/code/data
        if isinstance(error, CustomException):
            return json(Response(
                code=error.code,
                message=error.message,
                data=error.data if error.data is not None else {},
            ))

        # 3) Otherwise, it may be a system/DB exception; in dev re-raise, else return FAIL
        if self.debug or os.getenv("FLASK_ENV") == "development":
            raise error
        else:
            return json(Response(
                code=HttpCode.FAIL,
                message=str(error),
                data={},
            ))
