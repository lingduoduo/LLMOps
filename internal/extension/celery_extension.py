#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : celery_extension.py
"""
from celery import Task, Celery
from flask import Flask


def init_app(app: Flask):
    """Initialize the Celery configuration service"""

    class FlaskTask(Task):
        """
        Define FlaskTask to ensure Celery runs inside
        the Flask application context. This way,
        Flask configurations, databases, and other
        resources can be accessed within Celery tasks.
        """

        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    # 1. Create the Celery application and configure it
    celery_app = Celery(app.name, task_cls=FlaskTask)
    celery_app.config_from_object(app.config["CELERY"])
    celery_app.set_default()

    # 2. Attach Celery to the Flask app’s extensions
    app.extensions["celery"] = celery_app
