#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : 1.blob_parser_example.py
"""
from typing import Iterator

from langchain_core.document_loaders import Blob
from langchain_core.document_loaders.base import BaseBlobParser
from langchain_core.documents import Document


class CustomParser(BaseBlobParser):
    """A custom parser that converts each line of binary text data from a Blob into a Document."""

    def lazy_parse(self, blob: Blob) -> Iterator[Document]:
        line_number = 0
        with blob.as_bytes_io() as f:
            for line in f:
                yield Document(
                    page_content=line,
                    metadata={"source": blob.source, "line_number": line_number}
                )
                line_number += 1


# 1. Load the blob data
blob = Blob.from_path("meow_meow.txt")
parser = CustomParser()

# 2. Parse to get document objects
documents = list(parser.lazy_parse(blob))

# 3. Print the results
print(documents)
print(len(documents))
print(documents[0].metadata)
