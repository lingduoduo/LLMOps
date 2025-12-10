#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : analysis_handler.py
"""
from dataclasses import dataclass
from uuid import UUID

from flask_login import current_user
from injector import inject

from internal.service import AnalysisService
from pkg.response import success_json


@inject
@dataclass
class AnalysisHandler:
    """Analysis Processor"""
    analysis_service: AnalysisService

    def get_app_analysis(self, app_id: UUID):
        """Get application analysis data"""
        app_analysis = self.analysis_service.get_app_analysis(app_id, current_user)
        return success_json(app_analysis)
