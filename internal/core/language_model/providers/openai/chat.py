#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : chat.py
"""
from langchain_openai import ChatOpenAI

from internal.core.language_model.entities.model_entity import BaseLanguageModel


class Chat(ChatOpenAI, BaseLanguageModel):
    """OpenAI Chat Models"""
    pass
