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
