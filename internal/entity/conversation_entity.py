#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : conversation_entity.py
"""
from enum import Enum

from langchain_core.pydantic_v1 import BaseModel, Field

# Summary generation template
SUMMARIZER_TEMPLATE = """Incrementally summarize the provided conversation content, 
building upon the previous summary to produce an updated one.

EXAMPLE
Current summary:
The human asks the AI for its opinion on artificial intelligence. 
The AI believes that artificial intelligence is a force for good.

New conversation:
Human: Why do you think artificial intelligence is a force for good?
AI: Because artificial intelligence will help humans realize their full potential.

New summary:
The human asks the AI for its opinion on artificial intelligence. 
The AI believes AI is a force for good because it helps humans reach their full potential.
END OF EXAMPLE

Current summary:
{summary}

New conversation:
{new_lines}

New summary:"""

# Conversation name extraction template
CONVERSATION_NAME_TEMPLATE = "Extract the main topic from the user's message."


class ConversationInfo(BaseModel):
    """You need to break down the user's input into 'topic' and 'intent'
    to accurately identify the meaning of the message.

    Note:
    The user’s language can vary — it may be English, Chinese, Japanese, French, etc.
    Ensure your output matches the user’s language as closely as possible
    and keep it short, clear, and natural.

    Example 1:
    User input: hi, my name is Ling.
    {
        "language_type": "The user's input is purely English.",
        "reasoning": "The output language should be English.",
        "subject": "User introduces themselves."
    }

    Example 2:
    User input: hello
    {
        "language_type": "The user's input is purely English.",
        "reasoning": "The output language should be English.",
        "subject": "User greets the AI."
    }

    Example 3:
    User input: What does www.google.com talk about?
    {
        "language_type": "The user's input is purely English.",
        "reasoning": "The question is entirely in English.",
        "subject": "User asks about the content of www.google.com."
    }

    Example 4:
    User input: Why is Lucy older than Tom?
    {
        "language_type": "The user's input is purely English.",
        "reasoning": "The main intent is to compare ages.",
        "subject": "User asks about the ages of Lucy and Tom."
    }

    Example 5:
    User input: Hey, how are you today?
    {
        "language_type": "The user's input is purely English.",
        "reasoning": "The user is greeting in a casual tone.",
        "subject": "User asks how the AI is doing today."
    }
    """
    language_type: str = Field(description="The detected language type of the user’s input.")
    reasoning: str = Field(description="Explanation of how the language type was determined.")
    subject: str = Field(
        description=(
            "A brief summary describing the user’s intent and topic. "
            "The output language must match the input language, and it should be concise and clear. "
            "If the question is directed toward the AI itself, you may respond in a friendly or playful tone."
        )
    )


# Suggested question generation template
SUGGESTED_QUESTIONS_TEMPLATE = (
    "Based on the conversation history, predict the three most likely questions "
    "the user might ask next."
)


class SuggestedQuestions(BaseModel):
    """Predict the three most likely questions the user will ask next.
    Each question must be within 50 characters.
    The output must strictly follow this JSON array format:
    [\"Question 1\", \"Question 2\", \"Question 3\"]"""
    questions: list[str] = Field(description="A list of suggested questions as strings.")


class InvokeFrom(str, Enum):
    """Source of conversation invocation."""
    SERVICE_API = "service_api"  # External API call
    WEB_APP = "web_app"  # Web application
    DEBUGGER = "debugger"  # Debugging interface


class MessageStatus(str, Enum):
    """Conversation message status."""
    NORMAL = "normal"  # Normal
    STOP = "stop"  # Stopped
    ERROR = "error"  # Error occurred
