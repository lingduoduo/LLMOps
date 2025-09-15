#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : cos_service.py
"""
import hashlib
import os
import uuid
from dataclasses import dataclass
from datetime import datetime

from injector import inject
from qcloud_cos import CosS3Client, CosConfig
from werkzeug.datastructures import FileStorage

from internal.entity.upload_file_entity import ALLOWED_IMAGE_EXTENSION, ALLOWED_DOCUMENT_EXTENSION
from internal.exception import FailException
from internal.model import UploadFile
from .upload_file_service import UploadFileService


@inject
@dataclass
class CosService:
    """Tencent Cloud COS object storage service"""
    upload_file_service: UploadFileService

    def upload_file(self, file: FileStorage, only_image: bool = False) -> UploadFile:
        """Upload a file to Tencent Cloud COS and return the file metadata"""
        # TODO: Switch once the authentication/authorization module is finished
        account_id = "46db30d1-3199-4e79-a0cd-abf12fa6858f"

        # 1) Extract file extension and check if upload is allowed
        filename = file.filename
        extension = filename.rsplit(".", 1)[-1] if "." in filename else ""
        if extension.lower() not in (ALLOWED_IMAGE_EXTENSION + ALLOWED_DOCUMENT_EXTENSION):
            raise FailException(f"Files with .{extension} extension are not allowed to be uploaded")
        elif only_image and extension not in ALLOWED_IMAGE_EXTENSION:
            raise FailException(f"Files with .{extension} extension are not supported. Please upload a valid image")

        # 2) Get client and bucket name
        client = self._get_client()
        bucket = self._get_bucket()

        # 3) Generate a random file name
        random_filename = str(uuid.uuid4()) + "." + extension
        now = datetime.now()
        upload_filename = f"{now.year}/{now.month:02d}/{now.day:02d}/{random_filename}"

        # 4) Stream-read the file content
        file_content = file.stream.read()

        try:
            # 5) Upload the data to the COS bucket
            client.put_object(bucket, file_content, upload_filename)
        except Exception as e:
            raise FailException("File upload failed. Please try again later")

        # 6) Create the upload_file record
        return self.upload_file_service.create_upload_file(
            account_id=account_id,
            name=filename,
            key=upload_filename,
            size=len(file_content),
            extension=extension,
            mime_type=file.mimetype,
            hash=hashlib.sha3_256(file_content).hexdigest(),
        )

    def download_file(self, key: str, target_file_path: str):
        """Download a file from COS to the specified local path"""
        client = self._get_client()
        bucket = self._get_bucket()

        client.download_file(bucket, key, target_file_path)

    @classmethod
    def get_file_url(cls, key: str) -> str:
        """Get the public URL for a COS object by its key"""
        cos_domain = os.getenv("COS_DOMAIN")

        if not cos_domain:
            bucket = os.getenv("COS_BUCKET")
            scheme = os.getenv("COS_SCHEME")
            region = os.getenv("COS_REGION")
            cos_domain = f"{scheme}://{bucket}.cos.{region}.myqcloud.com"

        return f"{cos_domain}/{key}"

    @classmethod
    def _get_client(cls) -> CosS3Client:
        """Get the Tencent Cloud COS client"""
        conf = CosConfig(
            Region=os.getenv("COS_REGION"),
            SecretId=os.getenv("COS_SECRET_ID"),
            SecretKey=os.getenv("COS_SECRET_KEY"),
            Token=None,
            Scheme=os.getenv("COS_SCHEME", "https")
        )
        return CosS3Client(conf)

    @classmethod
    def _get_bucket(cls) -> str:
        """Get the bucket name"""
        return os.getenv("COS_BUCKET")
