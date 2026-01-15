#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : 1.custom_loader_example.py
"""
from typing import Iterator, AsyncIterator

from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document


class CustomDocumentLoader(BaseLoader):
    """A custom document loader that parses each line of a text file into a Document."""

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path

    def lazy_load(self) -> Iterator[Document]:
        # 1. Open the specified file
        with open(self.file_path, encoding="utf-8") as f:
            line_number = 0
            # 2. Iterate over each line in the file
            for line in f:
                # 3. Yield a Document for each line, including metadata
                yield Document(
                    page_content=line,
                    metadata={"source": self.file_path, "line_number": line_number}
                )
                line_number += 1

    async def alazy_load(self) -> AsyncIterator[Document]:
        import aiofiles
        # 1. Asynchronously open the file
        async with aiofiles.open(self.file_path, encoding="utf-8") as f:
            line_number = 0
            # 2. Iterate over each line asynchronously
            async for line in f:
                # 3. Yield a Document per line with metadata
                yield Document(
                    page_content=line,
                    metadata={"source": self.file_path, "line_number": line_number}
                )
                line_number += 1


# Usage example
loader = CustomDocumentLoader("meow_meow.txt")
documents = loader.load()

print(documents)
print(len(documents))
print(documents[0].metadata)
