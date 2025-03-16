#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : 1.summary_buffer_memory.py
"""
from typing import Any

import dotenv
from openai import OpenAI

dotenv.load_dotenv()


# 1. max_tokens is used to determine if a new summary needs to be generated
# 2. summary stores the summary information
# 3. chat_histories stores the conversation history
# 4. get_num_tokens calculates the number of tokens in the input text
# 5. save_context stores new conversation details
# 6. get_buffer_string converts historical conversation data to a string
# 7. load_memory_variables loads memory variable information
# 8. summary_text generates a new summary using the old summary and the new conversation
class ConversationSummaryBufferMemory:
    """Summary Buffer Mixed Memory Class"""

    def __init__(self, summary: str = '', chat_histories: list = None, max_tokens: int = 300):
        self.summary = summary
        self.chat_histories = [] if chat_histories is None else chat_histories
        self.max_tokens = max_tokens
        self._client = OpenAI(base_url='https://api.xty.app/v1')

    @classmethod
    def get_num_tokens(cls, query: str) -> int:
        """Calculate the number of tokens in the given query"""
        return len(query)

    def save_context(self, human_query: str, ai_content: str) -> None:
        """Save the new conversation details"""
        self.chat_histories.append({"human": human_query, "ai": ai_content})

        buffer_string = self.get_buffer_string()
        tokens = self.get_num_tokens(buffer_string)

        if tokens > self.max_tokens:
            first_chat = self.chat_histories[0]
            print("Generating new summary~")
            self.summary = self.summary_text(
                self.summary,
                f"Human:{first_chat.get('human')}\nAI:{first_chat.get('ai')}"
            )
            print("New summary generated successfully:", self.summary)
            del self.chat_histories[0]

    def get_buffer_string(self) -> str:
        """Convert historical conversation data into a string"""
        buffer: str = ""
        for chat in self.chat_histories:
            buffer += f"Human:{chat.get('human')}\nAI:{chat.get('ai')}\n\n"
        return buffer.strip()

    def load_memory_variables(self) -> dict[str, Any]:
        """Load memory variables as a dictionary for easier formatting in the prompt"""
        buffer_string = self.get_buffer_string()
        return {
            "chat_history": f"Summary:{self.summary}\n\nHistorical Info:{buffer_string}\n"
        }

    def summary_text(self, origin_summary: str, new_line: str) -> str:
        """Generate a new summary using the old summary and new conversation"""
        prompt = f"""You are a powerful chatbot. Please summarize the conversation content provided by the user,
        add it to the previously provided summary, and return a new summary. Do not generate any data except the new summary.
        If the user's conversation includes key information such as names, gender, locations, important events, etc., be sure to include them in the new summary.
        The summary should aim to preserve the user's conversation details as accurately as possible.

<example>
Current Summary: Humans ask AI about AI's perspective on artificial intelligence, and AI believes AI is a force for good.

New Conversation:
Human: What is our 401k?
AI:....

New Summary: Humans ask AI about AI's perspective on artificial intelligence, and AI believes AI is a force for good because it will help humans fully realize their potential.
</example>

===================== Below is the actual data to be processed =====================

Current Summary: {origin_summary}

New Conversation:
{new_line}

Please generate a new summary for the user based on the above information."""

        completion = self._client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return completion.choices[0].message.content


# 1. Create OpenAI client
client = OpenAI(base_url='https://api.xty.app/v1')
memory = ConversationSummaryBufferMemory("", [], 300)

# 2. Create an infinite loop for human-AI conversation
while True:
    # 3. Get human input
    query = input('Human: ')

    # 4. Check if input is 'q', if yes then exit
    if query == 'q':
        break

    # 5. Send request to OpenAI API to get AI-generated content
    memory_variables = memory.load_memory_variables()
    answer_prompt = (
        "You are a powerful chatbot. Please answer the user's question based on the provided context.\n\n"
        f"{memory_variables.get('chat_history')}\n\n"
        f"User's question: {query}"
    )
    response = client.chat.completions.create(
        model='gpt-4-turbo',
        messages=[
            {"role": "user", "content": answer_prompt},
        ],
        stream=True,
    )

    # 6. Loop through the streamed response content
    print("AI: ", flush=True, end="")
    ai_content = ""
    for chunk in response:
        content = chunk.choices[0].delta.content
        if content is None:
            break
        ai_content += content
        print(content, flush=True, end="")
    print("")
    memory.save_context(query, ai_content)
