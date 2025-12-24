#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : semantic_chunker_example.py
"""
import dotenv
import langchain_community.utils.math as math_utils
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity as sklearn_cosine_similarity

# Monkey-patch langchain's cosine_similarity to avoid simd error
math_utils.cosine_similarity = lambda X, Y: sklearn_cosine_similarity(np.array(X), np.array(Y))

from langchain_community.document_loaders import UnstructuredFileLoader
from langchain_experimental.text_splitter import SemanticChunker
from langchain_openai import OpenAIEmbeddings

# Load environment variables
dotenv.load_dotenv()

# 1. Initialize the loader and semantic chunker
loader = UnstructuredFileLoader("./science_fiction_short_story.txt")
text_splitter = SemanticChunker(
    embeddings=OpenAIEmbeddings(model="text-embedding-3-small"),
    # number_of_chunks=10,
    add_start_index=True,
    sentence_split_regex=r"(?<=[。？！.?!])"
)

# 2. Load the text and split into semantic chunks
documents = loader.load()
chunks = text_splitter.split_documents(documents)

# 3. Print out the size and metadata of each chunk
for chunk in chunks:
    print(f"Chunk size: {len(chunk.page_content)}, Metadata: {chunk.metadata}")

# !/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : html_header_text_splitter_example.py
"""
from langchain_text_splitters import HTMLHeaderTextSplitter

# 1. Define the HTML content and header levels for splitting
html_string = """
<!DOCTYPE html>
<html>
<body>
    <div>
        <h1>Title 1</h1>
        <p>Some introductory text about Title 1.</p>
        <div>
            <h2>Subtitle 1</h2>
            <p>Some introductory text about Subtitle 1.</p>
            <h3>Sub-subtitle 1</h3>
            <p>Some text about Sub-subtitle 1.</p>
            <h3>Sub-subtitle 2</h3>
            <p>Some text about Sub-subtitle 2.</p>
        </div>
        <div>
            <h3>Subtitle 2</h3>
            <p>Some text about Subtitle 2.</p>
        </div>
        <br>
        <p>Some closing text for Title 1.</p>
    </div>
</body>
</html>
"""
headers_to_split_on = [
    ("h1", "Level 1 Header"),
    ("h2", "Level 2 Header"),
    ("h3", "Level 3 Header"),
]

# 2. Initialize the splitter and split the HTML string
text_splitter = HTMLHeaderTextSplitter(headers_to_split_on)
chunks = text_splitter.split_text(html_string)

# 3. Output each chunk
for chunk in chunks:
    print(chunk)

# !/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : recursive_json_splitter_example.py
"""
import json

import requests
from langchain_text_splitters import RecursiveJsonSplitter

# 1. Fetch and load JSON from a remote URL
url = "https://api.smith.langchain.com/openapi.json"
json_data = requests.get(url).json()
# Print the length of the raw JSON string
print(len(json.dumps(json_data)))

# 2. Initialize the recursive JSON splitter
text_splitter = RecursiveJsonSplitter(max_chunk_size=300)

# 3. Split the JSON data into chunks and create Document objects
json_chunks = text_splitter.split_json(json_data)
chunks = text_splitter.create_documents(json_chunks)

for chunk in chunks[:3]:
    print(chunk.page_content)

# 4. Calculate and print the total length of all chunk contents
total_length = sum(len(chunk.page_content) for chunk in chunks)
print(total_length)

# !/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : token_based_splitter_example.py
"""
import tiktoken
from langchain_community.document_loaders import UnstructuredFileLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter


def calculate_token_count(text: str) -> int:
    """Calculate the number of tokens for the given text using tiktoken"""
    encoding = tiktoken.encoding_for_model("text-embedding-3-large")
    return len(encoding.encode(text))


# 1. Initialize the loader and recursive character splitter with token-based length function
loader = UnstructuredFileLoader("./science_fiction_short_story.txt")
text_splitter = RecursiveCharacterTextSplitter(
    separators=[
        "\n\n",  # Double newline
        "\n",  # Single newline
        "。|！|？",  # Chinese punctuation marks
        "\.\s|!\s|\?\s",  # English punctuation followed by space
        "；|;\s",  # Chinese/English semicolon
        "，|,\s",  # Chinese/English comma
        " ",  # Space
        ""  # Fallback: empty separator
    ],
    is_separator_regex=True,
    chunk_size=500,
    chunk_overlap=50,
    length_function=calculate_token_count,
)

# 2. Load the document and split into chunks
documents = loader.load()
chunks = text_splitter.split_documents(documents)

# 3. Print chunk sizes and metadata
for chunk in chunks:
    print(f"Chunk size: {len(chunk.page_content)}, Metadata: {chunk.metadata}")
