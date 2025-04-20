#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : custom_text_splitter_example.py
"""
import string
from typing import List

import nltk
from langchain_community.document_loaders import UnstructuredFileLoader
from langchain_text_splitters import TextSplitter
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

# Ensure required NLTK data is available
nltk.download('punkt')
nltk.download('stopwords')


class CustomTextSplitter(TextSplitter):
    """A custom text splitter that extracts top keywords from each segment using NLTK."""

    def __init__(self, separator: str, top_k: int = 10, **kwargs):
        """
        Initialize with a separator string and number of keywords to extract per segment.
        :param separator: The string to split the text on.
        :param top_k: Number of top keywords to extract from each split segment (default 10).
        """
        super().__init__(**kwargs)
        self._separator = separator
        self._top_k = top_k
        self._stopwords = set(stopwords.words('english'))
        self._punct_table = str.maketrans('', '', string.punctuation)

    def split_text(self, text: str) -> List[str]:
        """
        Split the input text using the separator, extract keywords from each segment,
        and return a list of comma-separated keyword strings per segment.
        :param text: The full text to split and analyze.
        :return: List of keyword strings for each segment.
        """
        segments = text.split(self._separator)
        keyword_chunks: List[str] = []
        for segment in segments:
            # Tokenize and normalize
            tokens = word_tokenize(segment.lower())
            # Remove punctuation and stopwords
            cleaned = [t.translate(self._punct_table) for t in tokens]
            filtered = [t for t in cleaned if t.isalpha() and t not in self._stopwords]
            # Compute frequency distribution and get top K
            freq_dist = nltk.FreqDist(filtered)
            top_keywords = [word for word, _ in freq_dist.most_common(self._top_k)]
            keyword_chunks.append(",".join(top_keywords))
        return keyword_chunks


# 1. Initialize loader and custom splitter
loader = UnstructuredFileLoader("./science_fiction_short_story.txt")
splitter = CustomTextSplitter(separator="\n\n", top_k=10)

# 2. Load the document and split into keyword chunks
documents = loader.load()
keyword_chunks = splitter.split_documents(documents)

# 3. Print keyword string for each chunk
for chunk in keyword_chunks:
    print(chunk.page_content)
