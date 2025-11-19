#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : upload_file_handler.py
"""
from dataclasses import dataclass

from flask_login import login_required, current_user
from injector import inject

from internal.schema.upload_file_schema import UploadFileReq, UploadFileResp, UploadImageReq
from internal.service import S3Service
from pkg.response import validate_error_json, success_json


@inject
@dataclass
class UploadFileHandler:
    """Upload File Handler"""
    s3_service: S3Service

    @login_required
    def upload_file(self):
        """Upload a file/document"""
        # 1) Build request and validate
        req = UploadFileReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2) Call service to upload the file and get the record
        upload_file = self.s3_service.upload_file(req.file.data, current_user)

        # 3) Build response and return
        resp = UploadFileResp()
        return success_json(resp.dump(upload_file))

    @login_required
    def upload_image(self):
        """Upload an image"""
        # 1) Build request and validate
        req = UploadImageReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2) Call service and upload the file
        upload_file = self.s3_service.upload_file(req.file.data, True, current_user)

        # 3) Get the actual URL of the image
        image_url = self.s3_service.get_file_url(upload_file.key)

        return success_json({"image_url": image_url})
