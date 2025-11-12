#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshe@gmail.com
@File    : app.py
"""
import dotenv
from flask_login import LoginManager
from flask_migrate import Migrate
from injector import Injector

from config import Config
from internal.middleware import Middleware
from internal.router import Router
from internal.server import Http
from pkg.sqlalchemy import SQLAlchemy
from .module import ExtensionModule

# import .env
dotenv.load_dotenv()

conf = Config()

injector = Injector([ExtensionModule])

app = Http(
    __name__,
    conf=conf,
    db=injector.get(SQLAlchemy),
    migrate=injector.get(Migrate),
    login_manager=injector.get(LoginManager),
    middleware=injector.get(Middleware),
    router=injector.get(Router),
)

celery = app.extensions['celery']

if __name__ == "__main__":
    app.run(debug=True)
