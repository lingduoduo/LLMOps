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

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from injector import inject
from werkzeug.datastructures import FileStorage

from internal.entity.upload_file_entity import ALLOWED_IMAGE_EXTENSION, ALLOWED_DOCUMENT_EXTENSION
from internal.exception import FailException
from internal.model import UploadFile
from .upload_file_service import UploadFileService


@inject
@dataclass
class S3Service:
    """AWS S3 object storage service"""
    upload_file_service: UploadFileService

    def upload_file(self, file: FileStorage, only_image: bool = False) -> UploadFile:
        """Upload a file to AWS S3 and return the file metadata"""
        # TODO: Switch once the authentication/authorization module is finished
        account_id = "46db30d1-3199-4e79-a0cd-abf12fa6858f"

        # 1) Extract file extension and check if upload is allowed
        filename = file.filename or ""
        extension = filename.rsplit(".", 1)[-1] if "." in filename else ""
        ext_lc = extension.lower()

        if ext_lc not in (ALLOWED_IMAGE_EXTENSION + ALLOWED_DOCUMENT_EXTENSION):
            raise FailException(f"Files with .{extension} extension are not allowed to be uploaded")
        elif only_image and ext_lc not in ALLOWED_IMAGE_EXTENSION:
            raise FailException(f"Files with .{extension} extension are not supported. Please upload a valid image")

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
            # preserve content-type if available
            if file.mimetype:
                put_kwargs["ContentType"] = file.mimetype

            # Optional: set ACL if you want objects to be public by default
            # ACL = os.getenv("S3_OBJECT_ACL")  # e.g. "public-read"
            # if ACL:
            #     put_kwargs["ACL"] = ACL

            s3.put_object(**put_kwargs)

        except (BotoCoreError, ClientError) as e:
            raise FailException("File upload failed. Please try again later") from e

        # 6) Create the upload_file DB record
        return self.upload_file_service.create_upload_file(
            account_id=account_id,
            name=filename,
            key=upload_key,
            size=len(file_content),
            extension=extension,
            mime_type=(file.mimetype or ""),
            hash=hashlib.sha3_256(file_content).hexdigest(),
        )

    def download_file(self, key: str, target_file_path: str):
        """Download a file from S3 to the specified local path"""
        s3 = self._get_client()
        bucket = self._get_bucket()
        try:
            s3.download_file(bucket, key, target_file_path)
        except (BotoCoreError, ClientError) as e:
            raise FailException("File download failed. Please try again later") from e

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
            raise FailException("S3 bucket not configured (S3_BUCKET)")

        if domain:
            # e.g., https://cdn.example.com/path/to/object
            base = domain.rstrip("/")
            return f"{base}/{key}"

        if not region:
            # Some SDKs can infer region automatically, but we need it to build the URL
            # Fall back to global endpoint (works in many cases, but region is recommended)
            return f"https://{bucket}.s3.amazonaws.com/{key}"

        # Virtual-hosted–style URL (recommended)
        return f"https://{bucket}.s3.{region}.amazonaws.com/{key}"

    @classmethod
    def _get_client(cls):
        """Get the AWS S3 client"""
        # If you use a custom endpoint (e.g., MinIO), set S3_ENDPOINT_URL
        endpoint_url = os.getenv("S3_ENDPOINT_URL")  # optional
        region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")

        # boto3 will pick up credentials from env (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN)
        # or from IAM role if running on AWS.
        session = boto3.session.Session(region_name=region)
        return session.client("s3", endpoint_url=endpoint_url)

    @classmethod
    def _get_bucket(cls) -> str:
        """Get the S3 bucket name"""
        bucket = os.getenv("S3_BUCKET")
        if not bucket:
            raise FailException("S3 bucket not configured (S3_BUCKET)")
        return bucket
