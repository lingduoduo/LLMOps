#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : chat.py
"""
from typing import Tuple

import tiktoken
from langchain_openai import ChatOpenAI

from internal.core.language_model.entities.model_entity import BaseLanguageModel


class Chat(ChatOpenAI, BaseLanguageModel):
    """OpenAI Chat Models"""

    def _get_encoding_model(self) -> Tuple[str, tiktoken.Encoding]:
        """
        Return (model_name, encoding) safely.
        If the model is not recognized by tiktoken, fallback to cl100k_base.
        """
        model = getattr(self, "model", "gpt-4o")

        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            # Fallback for new or unknown models
            encoding = tiktoken.get_encoding("cl100k_base")

        return model, encoding
