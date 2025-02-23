#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2024/4/6 21:08
@Author  : linghypshen@gmail.com
@File    : sqlalchemy.py
"""
from contextlib import contextmanager

from flask_sqlalchemy import SQLAlchemy as _SQAlchemy


class SQLAlchemy(_SQAlchemy):
    """重写Flask-SQLAlchemy中的核心类，实现自动提交"""

    @contextmanager
    def auto_commit(self):
        try:
            yield
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            raise e
