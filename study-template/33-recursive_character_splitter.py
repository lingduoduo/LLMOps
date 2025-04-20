#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : recursive_character_splitter_example.py
"""
from langchain_community.document_loaders import UnstructuredMarkdownLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# 1. Load the target document
loader = UnstructuredMarkdownLoader("project_api_docs.md")
documents = loader.load()

# 2. Initialize the recursive text splitter
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
    add_start_index=True,
)

# 3. Split the documents into chunks
chunks = text_splitter.split_documents(documents)

for chunk in chunks:
    print(f"Chunk size: {len(chunk.page_content)}, Metadata: {chunk.metadata}")

# !/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : recursive_code_splitter_example.py
"""
from langchain_community.document_loaders import UnstructuredFileLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter, Language

# 1. Load the source code file
loader = UnstructuredFileLoader("demo.py")
documents = loader.load()

# 2. Initialize a recursive character splitter for Python code
text_splitter = RecursiveCharacterTextSplitter.from_language(
    language=Language.PYTHON,
    chunk_size=500,
    chunk_overlap=50,
    add_start_index=True,
)

# 3. Split the code into chunks
chunks = text_splitter.split_documents(documents)

# 4. Output chunk sizes and metadata
for chunk in chunks:
    print(f"Chunk size: {len(chunk.page_content)}, Metadata: {chunk.metadata}")

# 5. Print the content of the third chunk
print(chunks[2].page_content)

# !/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Example: Recursive Character Text Splitter with Custom Separators
"""
from langchain_community.document_loaders import UnstructuredMarkdownLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# 1. Initialize loader and define custom separators
loader = UnstructuredMarkdownLoader("./project_api_docs.md")
separators = [
    "\n\n",  # Double newline
    "\n",  # Single newline
    "。|！|？",  # Chinese punctuation: period, exclamation, question
    "\.\s|!\s|\?\s",  # English punctuation followed by space
    "；|;\s",  # Chinese and English semicolon
    "，|,\s",  # Chinese and English comma
    " ",  # Space
    ""  # Fallback: empty string
]
text_splitter = RecursiveCharacterTextSplitter(
    separators=separators,
    is_separator_regex=True,
    chunk_size=500,
    chunk_overlap=50,
    add_start_index=True,
)

# 2. Load documents and split into chunks
documents = loader.load()
chunks = text_splitter.split_documents(documents)

# 3. Print chunk size and metadata
for chunk in chunks:
    print(f"Chunk size: {len(chunk.page_content)}, Metadata: {chunk.metadata}")
