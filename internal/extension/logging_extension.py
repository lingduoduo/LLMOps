#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : logging_extension.py
"""
import logging
import os.path

from concurrent_log_handler import ConcurrentTimedRotatingFileHandler
from flask import Flask


def init_app(app: Flask):
    """Initialize the application logger."""
    # 1. Set the log level of the root logger based on the environment
    logging.getLogger().setLevel(
        logging.DEBUG if app.debug or os.getenv("FLASK_ENV") == "development" else logging.WARNING
    )

    # 2. Set up the log directory; create it if it does not exist
    log_folder = os.path.join(os.getcwd(), "storage", "log")
    if not os.path.exists(log_folder):
        os.makedirs(log_folder)

    # 3. Define the log file name
    log_file = os.path.join(log_folder, "app.log")

    # 4. Configure log formatting and enable daily log rotation
    handler = ConcurrentTimedRotatingFileHandler(
        log_file,
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    formatter = logging.Formatter(
        "[%(asctime)s.%(msecs)03d] %(filename)s -> %(funcName)s line:%(lineno)d "
        "[%(levelname)s]: %(message)s"
    )
    handler.setLevel(
        logging.DEBUG if app.debug or os.getenv("FLASK_ENV") == "development" else logging.WARNING
    )
    handler.setFormatter(formatter)
    logging.getLogger().addHandler(handler)

    # 5. In development mode, also output logs to the console
    if app.debug or os.getenv("FLASK_ENV") == "development":
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logging.getLogger().addHandler(console_handler)
