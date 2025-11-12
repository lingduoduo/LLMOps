#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : schema.py
"""
from wtforms import Field


class ListField(Field):
    """Custom list field for storing list-type data"""
    data: list = None

    def process_formdata(self, valuelist):
        if valuelist is not None and isinstance(valuelist, list):
            self.data = valuelist

    def _value(self):
        return self.data if self.data else []


class DictField(Field):
    """Dictionary field for storing dict-type data"""
    data: dict = None

    def process_formdata(self, valuelist):
        if valuelist is not None and len(valuelist) > 0 and isinstance(valuelist[0], dict):
            self.data = valuelist[0]

    def _value(self):
        return self.data
