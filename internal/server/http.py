#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : http.py
"""
import os

from flask import Flask
from flask_migrate import Migrate

from config import Config
from internal.exception import CustomException
from internal.router import Router
from pkg.response import json, Response, HttpCode
from pkg.sqlalchemy import SQLAlchemy


class Http(Flask):
    """HTTP Service Engine"""

    def __init__(
            self,
            *args,
            conf: Config,
            db: SQLAlchemy,
            migrate: Migrate,
            router: Router,
            **kwargs,
    ):
        # 1. Call the parent class constructor for initialization
        super().__init__(*args, **kwargs)

        # 2. Initialize application configuration
        self.config.from_object(conf)

        # 3. Register and bind error handlers
        self.register_error_handler(Exception, self._register_error_handler)

        # 4. Initialize Flask extensions
        # db.init_app(self)
        # migrate.init_app(self, db, directory="internal/migration")

        # 5. Register application routes
        router.register_router(self)

    def _register_error_handler(self, error: Exception):
        # 1. Check if the exception is a custom exception; if so, extract the message and code
        if isinstance(error, CustomException):
            return json(Response(
                code=error.code,
                message=error.message,
                data=error.data if error.data is not None else {},
            ))
        # 2. If it's not a custom exception, it might be an exception thrown by the program or database.
        #    Extract the information and set the response code to FAIL.
        if self.debug or os.getenv("FLASK_ENV") == "development":
            raise error
        else:
            return json(Response(
                code=HttpCode.FAIL,
                message=str(error),
                data={},
            ))
