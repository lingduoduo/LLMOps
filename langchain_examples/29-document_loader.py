#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2024/7/1 18:35
@File    : 1.markdown_document_loader.py
"""
from langchain_community.document_loaders import UnstructuredMarkdownLoader

# 1. Create the Markdown loader
loader = UnstructuredMarkdownLoader("project_api_docs.md")

# 2. Load the documents
documents = loader.load()

print(documents)
print(len(documents))
print(documents[0].metadata)

# !/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2024/7/1 18:46
@File    : 2.office_document_loader.py
"""

# Example Excel loader (commented out):
from langchain_community.document_loaders import UnstructuredExcelLoader, UnstructuredPowerPointLoader

excel_loader = UnstructuredExcelLoader("./staff_attendance.xlsx", mode="elements")
excel_documents = excel_loader.load()

print(excel_documents)
print(len(excel_documents))

# Example Word loader (commented out):
from langchain_community.document_loaders import UnstructuredWordDocumentLoader

word_loader = UnstructuredWordDocumentLoader("./meow_meow.docx")
documents = word_loader.load()

print(documents)
print(len(documents))

# 1. Create the PowerPoint loader
ppt_loader = UnstructuredPowerPointLoader("./chapter_introduction.pptx")

# 2. Load the slides
documents = ppt_loader.load()

print(documents)
print(len(documents))
print(documents[0].metadata)

# !/usr/bin/env python
# -*- coding: utf-8 -*-
# """
# @Time    : 2024/7/1 23:17
# @File    : 3.WebBaseLoader.py
# """
from langchain_community.document_loaders import WebBaseLoader

loader = WebBaseLoader("https://google.com")
documents = loader.load()

print(documents)
print(len(documents))
print(documents[0].metadata)

# !/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2024/7/1 23:30
@File    : 4.UnstructuredFileLoader.py
"""
from langchain_community.document_loaders import UnstructuredFileLoader

loader = UnstructuredFileLoader("./project_api_docs.md")
documents = loader.load()

print(documents)
print(len(documents))
print(documents[0].metadata)
