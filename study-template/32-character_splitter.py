#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : character_splitter_example.py
"""
from langchain_community.document_loaders import UnstructuredMarkdownLoader
from langchain_text_splitters import CharacterTextSplitter

# 1. Load the target document
loader = UnstructuredMarkdownLoader("project_api_docs.md")
documents = loader.load()

# 2. Initialize the text splitter
text_splitter = CharacterTextSplitter(
    separator="\n\n",
    chunk_size=800,
    chunk_overlap=50,
    add_start_index=True,
)

# 3. Split the documents into chunks
chunks = text_splitter.split_documents(documents)

for chunk in chunks:
    print(f"Chunk size: {len(chunk.page_content)}, Metadata: {chunk.metadata}")

# Print the total number of chunks
print(len(chunks))
