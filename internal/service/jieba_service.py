#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : jieba_service.py
"""
from dataclasses import dataclass

import jieba.analyse
from injector import inject
from jieba.analyse import default_tfidf

from internal.entity.jieba_entity import STOPWORD_SET


@inject
@dataclass
class JiebaService:
    """Jieba tokenizer/keyword-extraction service"""

    def __init__(self):
        """Constructor: extend Jieba's stopword list"""
        default_tfidf.stop_words = STOPWORD_SET

    @classmethod
    def extract_keywords(cls, text: str, max_keyword_pre_chunk: int = 10) -> list[str]:
        """Extract a list of keywords from the input text"""
        return jieba.analyse.extract_tags(
            sentence=text,
            topK=max_keyword_pre_chunk,
        )

#
# #!/usr/bin/env python
# # -*- coding: utf-8 -*-
# """
# EnglishKeywordService (NLTK)
# - Simpler frequency-based keyword extraction with stopwords filtering.
# - For best results, run once:
#     >>> import nltk
#     >>> nltk.download('punkt'); nltk.download('stopwords')
# """
# from dataclasses import dataclass
# from typing import Iterable, Optional, List
# from collections import Counter
# import re
#
# from injector import inject
#
# try:
#     import nltk
#     from nltk.corpus import stopwords
#     from nltk.tokenize import word_tokenize
# except ImportError as e:
#     raise ImportError(
#         "NLTK is required. Install with:\n"
#         "  pip install nltk\n"
#         "Then in Python:\n"
#         "  import nltk; nltk.download('punkt'); nltk.download('stopwords')"
#     ) from e
#
#
# @inject
# @dataclass
# class EnglishKeywordServiceNLTK:
#     """English keyword extraction service using NLTK (frequency + stopword filter)."""
#     _stopwords: set
#
#     def __init__(self, extra_stopwords: Optional[Iterable[str]] = None):
#         st = set(stopwords.words("english"))
#         if extra_stopwords:
#             st |= {w.lower() for w in extra_stopwords}
#         self._stopwords = st
#
#     def extract_keywords(self, text: str, max_keyword_pre_chunk: int = 10) -> List[str]:
#         if not text:
#             return []
#         # basic normalization
#         text = text.strip()
#
#         # tokenize words
#         tokens = [t.lower() for t in word_tokenize(text)]
#
#         # keep alphabetic tokens only & filter stopwords
#         tokens = [t for t in tokens if re.fullmatch(r"[a-z]+", t)]
#         tokens = [t for t in tokens if t not in self._stopwords]
#
#         counts = Counter(tokens)
#         # return highest-frequency tokens (ties broken by longer first)
#         ranked = sorted(counts.items(), key=lambda x: (-x[1], -len(x[0]), x[0]))
#         return [w for w, _ in ranked[:max_keyword_pre_chunk]]
