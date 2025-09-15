#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : logging_extension.py
"""
import logging
import os
from logging.handlers import TimedRotatingFileHandler

from flask import Flask


def init_app(app: Flask):
    """Initialize the logger"""
    # 1) Set the log folder; create it if it doesn't exist
    log_folder = os.path.join(os.getcwd(), "storage", "log")
    if not os.path.exists(log_folder):
        os.makedirs(log_folder)

    # 2) Define the log file name
    log_file = os.path.join(log_folder, "app.log")

    # 3) Set the log format and rotate daily
    handler = TimedRotatingFileHandler(
        log_file,
        when="midnight",
        interval=1,
        backupCount=30,  # keep 30 daily backups
        encoding="utf-8",
    )
    formatter = logging.Formatter(
        "[%(asctime)s.%(msecs)03d] %(filename)s -> %(funcName)s line:%(lineno)d [%(levelname)s]: %(message)s"
    )
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(formatter)
    logging.getLogger().addHandler(handler)

    # 4) In development, also output logs to the console
    if app.debug or os.getenv("FLASK_ENV") == "development":
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logging.getLogger().addHandler(console_handler)
