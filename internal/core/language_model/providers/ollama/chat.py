#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : chat.py
"""
from langchain_ollama import ChatOllama

from internal.core.language_model.entities.model_entity import BaseLanguageModel


class Chat(ChatOllama, BaseLanguageModel):
    """Ollama Chat Model"""
    pass
