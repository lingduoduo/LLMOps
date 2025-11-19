#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : file_extractor.py
"""
import os.path
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Union

import requests
from injector import inject
from langchain_community.document_loaders import (
    UnstructuredExcelLoader,
    UnstructuredPDFLoader,
    UnstructuredMarkdownLoader,
    UnstructuredHTMLLoader,
    UnstructuredCSVLoader,
    UnstructuredPowerPointLoader,
    UnstructuredXMLLoader,
    UnstructuredFileLoader,
    TextLoader,
)
from langchain_core.documents import Document as LCDocument

from internal.model import UploadFile
from internal.service import S3Service


@inject
@dataclass
class FileExtractor:
    """File extractor: load remote files or UploadFile records into LangChain Documents or plain text."""
    s3_service: S3Service

    def load(
            self,
            upload_file: UploadFile,
            return_text: bool = False,
            is_unstructured: bool = True,
    ) -> Union[list[LCDocument], str]:
        """Load the given UploadFile record and return either a list of LangChain Documents or a string."""
        # 1) Create a temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # 2) Build a temporary local file path
            file_path = os.path.join(temp_dir, os.path.basename(upload_file.key))

            # 3) Download the object storage file to local temp path
            self.s3_service.download_file(upload_file.key, file_path)

            # 4) Load the file from the specified path
            return self.load_from_file(file_path, return_text, is_unstructured)

    @classmethod
    def load_from_url(cls, url: str, return_text: bool = False) -> Union[list[LCDocument], str]:
        """Load data from the given URL and return a list of LangChain Documents or a string."""
        # 1) Download the remote file to memory
        response = requests.get(url)

        # 2) Save it into a local temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # 3) Determine the filename and write the remote content locally
            file_path = os.path.join(temp_dir, os.path.basename(url))
            with open(file_path, "wb") as file:
                file.write(response.content)

            return cls.load_from_file(file_path, return_text)

    @classmethod
    def load_from_file(
            cls,
            file_path: str,
            return_text: bool = False,
            is_unstructured: bool = True,
    ) -> Union[list[LCDocument], str]:
        """Load data from a local file and return a list of LangChain Documents or a string."""
        # 1) Get the file extension
        delimiter = "\n\n"
        file_extension = Path(file_path).suffix.lower()

        # 2) Choose an appropriate loader based on extension
        if file_extension in [".xlsx", ".xls"]:
            loader = UnstructuredExcelLoader(file_path)
        elif file_extension == ".pdf":
            loader = UnstructuredPDFLoader(file_path)
        elif file_extension in [".md", ".markdown"]:
            loader = UnstructuredMarkdownLoader(file_path)
        elif file_extension in [".htm", ".html"]:
            loader = UnstructuredHTMLLoader(file_path)
        elif file_extension == ".csv":
            loader = UnstructuredCSVLoader(file_path)
        elif file_extension in [".ppt", "pptx"]:
            loader = UnstructuredPowerPointLoader(file_path)
        elif file_extension == ".xml":
            loader = UnstructuredXMLLoader(file_path)
        else:
            loader = UnstructuredFileLoader(file_path) if is_unstructured else TextLoader(file_path)

        # 3) Return the loaded documents or concatenated text
        return (
            delimiter.join([document.page_content for document in loader.load()])
            if return_text
            else loader.load()
        )
