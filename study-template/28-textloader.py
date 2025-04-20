#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2024/7/1 15:27
@File    : 1.document_and_textloader.py
"""
from langchain_community.document_loaders import TextLoader

# 1. Build the loader
loader = TextLoader("ecommerce_product_data.txt", encoding="utf-8")

# 2. Load the data
documents = loader.load()

print(documents)
print(len(documents))
print(documents[0].metadata)
