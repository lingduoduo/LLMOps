#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : http.py
"""
import logging
import os

from flask import Flask
from flask_cors import CORS
from flask_login import LoginManager
from flask_migrate import Migrate

from config import Config
from internal.exception import CustomException
from internal.extension import logging_extension, redis_extension, celery_extension
from internal.middleware import Middleware
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
            login_manager: LoginManager,
            middleware: Middleware,
            router: Router,
            **kwargs,
    ):
        # 1) Call the parent constructor to initialize
        super().__init__(*args, **kwargs)

        # 2) Load application configuration
        self.config.from_object(conf)

        # 3) Register a global exception handler
        self.register_error_handler(Exception, self._register_error_handler)

        # 4) Initialize Flask extensions
        db.init_app(self)
        migrate.init_app(self, db, directory="internal/migration")
        redis_extension.init_app(self)
        celery_extension.init_app(self)
        logging_extension.init_app(self)
        login_manager.init_app(self)

        # 5) Enable CORS to resolve cross-origin requests between frontend & backend
        CORS(self, resources={
            r"/*": {
                "origins": "*",
                "supports_credentials": True,
                # "methods": ["GET", "POST"],
                # "allow_headers": ["Content-Type"],
            }
        })

        # 6) MiddleWare
        login_manager.request_loader(middleware.request_loader)

        # 7) Register application routes
        router.register_router(self)

    def _register_error_handler(self, error: Exception):
        # 1) Log the exception details
        logging.error("An error occurred: %s", error, exc_info=True)

        # 2) If this is our CustomException, extract message/code/etc.
        if isinstance(error, CustomException):
            return json(Response(
                code=error.code,
                message=error.message,
                data=error.data if error.data is not None else {},
            ))

        # 3) Otherwise, it may be a program/DB exception; expose details in dev,
        #    or return a FAIL status code in non-debug environments.
        if self.debug or os.getenv("FLASK_ENV") == "development":
            raise error
        else:
            return json(Response(
                code=HttpCode.FAIL,
                message=str(error),
                data={},
            ))
