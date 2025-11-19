#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : s3_service.py
"""
import hashlib
import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from injector import inject
from werkzeug.datastructures import FileStorage

from internal.entity.upload_file_entity import ALLOWED_IMAGE_EXTENSION, ALLOWED_DOCUMENT_EXTENSION
from internal.exception import FailException, ForbiddenException
from internal.model import Account, UploadFile
from .upload_file_service import UploadFileService


@inject
@dataclass
class S3Service:
    """AWS S3 object storage service"""
    upload_file_service: UploadFileService

    def upload_file(
            self,
            file: FileStorage,
            only_image: bool = False,
            account: Optional[Account] = None,
    ) -> UploadFile:
        """
        Upload a file to AWS S3 and return the file metadata.

        Only an authenticated/authorized account can upload files.
        """
        # 0) Basic authorization check
        if account is None or getattr(account, "id", None) is None:
            raise ForbiddenException("You are not authorized to upload files.")

        # 1) Extract file extension and check if upload is allowed
        filename = file.filename or ""
        extension = filename.rsplit(".", 1)[-1] if "." in filename else ""
        ext_lc = extension.lower()

        allowed_extensions = set(ALLOWED_DOCUMENT_EXTENSION) | set(ALLOWED_IMAGE_EXTENSION)
        if ext_lc not in allowed_extensions:
            raise FailException(f"Files with .{extension} extension are not allowed to be uploaded.")
        if only_image and ext_lc not in ALLOWED_IMAGE_EXTENSION:
            raise FailException(f"Files with .{extension} extension are not supported. Please upload a valid image.")

        # 2) Get client and bucket name
        s3 = self._get_client()
        bucket = self._get_bucket()

        # 3) Generate a random file name and partition by date
        random_filename = f"{uuid.uuid4()}.{extension}" if extension else str(uuid.uuid4())
        now = datetime.now()
        upload_key = f"{now.year}/{now.month:02d}/{now.day:02d}/{random_filename}"

        # 4) Read file content (bytes)
        file_content = file.stream.read()

        # 5) Upload to S3
        try:
            put_kwargs = {
                "Bucket": bucket,
                "Key": upload_key,
                "Body": file_content,
            }
            # Preserve content-type if available
            if file.mimetype:
                put_kwargs["ContentType"] = file.mimetype

            s3.put_object(**put_kwargs)
        except (BotoCoreError, ClientError) as e:
            raise FailException("File upload failed. Please try again later.") from e

        # 6) Create the upload_file DB record
        return self.upload_file_service.create_upload_file(
            account_id=account.id,
            name=filename,
            key=upload_key,
            size=len(file_content),
            extension=extension,
            mime_type=(file.mimetype or ""),
            hash=hashlib.sha3_256(file_content).hexdigest(),
        )

    def download_file(self, upload_file: UploadFile, account: Optional[Account], target_file_path: str) -> None:
        """
        Download a file from S3 to the specified local path.

        Only the owner account of the UploadFile record is allowed to download.
        """
        # 0) Authorization and ownership check
        if account is None or getattr(account, "id", None) is None:
            raise ForbiddenException("You are not authorized to download files.")

        if upload_file.account_id != account.id:
            raise ForbiddenException("You do not have permission to download this file.")

        s3 = self._get_client()
        bucket = self._get_bucket()

        try:
            s3.download_file(bucket, upload_file.key, target_file_path)
        except (BotoCoreError, ClientError) as e:
            raise FailException("File download failed. Please try again later.") from e

    @classmethod
    def get_file_url(cls, key: str) -> str:
        """
        Get the public URL for an S3 object by its key.

        Priority:
        - If S3_DOMAIN is set (e.g., your CloudFront or custom domain), use that.
        - Else build a standard regional S3 URL.
        """
        domain = os.getenv("S3_DOMAIN")
        bucket = os.getenv("S3_BUCKET")
        region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")

        if not bucket:
            raise FailException("S3 bucket not configured (S3_BUCKET).")

        if domain:
            # e.g., https://cdn.example.com/path/to/object
            base = domain.rstrip("/")
            return f"{base}/{key}"

        if not region:
            # Fallback global endpoint
            return f"https://{bucket}.s3.amazonaws.com/{key}"

        # Virtual-hosted–style URL (recommended)
        return f"https://{bucket}.s3.{region}.amazonaws.com/{key}"

    @classmethod
    def _get_client(cls):
        """Get the AWS S3 client."""
        endpoint_url = os.getenv("S3_ENDPOINT_URL")  # optional
        region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")

        session = boto3.session.Session(region_name=region)
        return session.client("s3", endpoint_url=endpoint_url)

    @classmethod
    def _get_bucket(cls) -> str:
        """Get the S3 bucket name."""
        bucket = os.getenv("S3_BUCKET")
        if not bucket:
            raise FailException("S3 bucket not configured (S3_BUCKET).")
        return bucket
