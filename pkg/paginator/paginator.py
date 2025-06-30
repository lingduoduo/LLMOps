#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : paginator.py
"""

import math
from dataclasses import dataclass
from typing import Any

from flask_wtf import FlaskForm
from wtforms import IntegerField
from wtforms.validators import Optional, NumberRange

from pkg.sqlalchemy import SQLAlchemy


class PaginatorReq(FlaskForm):
    """
    Base class for pagination requests.
    Includes current page number and page size.
    Any request needing pagination info can inherit from this class.
    """
    current_page = IntegerField(
        "current_page",
        default=1,
        validators=[
            Optional(),
            NumberRange(min=1, max=9999, message="Page number must be between 1 and 9999")
        ]
    )
    page_size = IntegerField(
        "page_size",
        default=20,
        validators=[
            Optional(),
            NumberRange(min=1, max=50, message="Page size must be between 1 and 50")
        ]
    )


@dataclass
class Paginator:
    """
    Paginator class.
    """
    total_page: int = 0  # Total number of pages
    total_record: int = 0  # Total number of records
    current_page: int = 1  # Current page number
    page_size: int = 20  # Number of records per page

    def __init__(self, db: SQLAlchemy, req: PaginatorReq = None):
        if req is not None:
            self.current_page = req.current_page.data
            self.page_size = req.page_size.data
        self.db = db

    def paginate(self, select) -> list[Any]:
        """
        Apply pagination to the given SQLAlchemy query.
        """
        # 1. Call db.paginate to paginate the results
        p = self.db.paginate(select, page=self.current_page, per_page=self.page_size, error_out=False)

        # 2. Compute total records and total pages
        self.total_record = p.total
        self.total_page = math.ceil(p.total / self.page_size)

        # 3. Return the paginated items
        return p.items


@dataclass
class PageModel:
    list: list[Any]
    paginator: Paginator
