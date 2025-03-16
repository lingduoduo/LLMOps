#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : 1.ConversationSummaryBufferMemory.py
"""
from typing import Any

import dotenv
from openai import OpenAI

dotenv.load_dotenv()


class ConversationSummaryBufferMemory:
    """Summary Buffer Mixed Memory Class"""

    # 1. max_tokens is used to determine if a new summary needs to be generated
    # 2. summary stores the summary information
    # 3. chat_histories stores the conversation history
    # 4. get_num_tokens calculates the number of tokens in the input text
    # 5. save_context stores new conversation details
    # 6. get_buffer_string converts historical conversation data to a string
    # 7. load_memory_variables loads memory variable information
    # 8. summary_text generates a new summary using the old summary and the new conversation

    def __init__(self, summary: str = '', chat_histories: list = None, max_tokens: int = 300):
        self.summary = summary
        self.chat_histories = [] if chat_histories is None else chat_histories
        self.max_tokens = max_tokens
        self._client = OpenAI()

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
client = OpenAI()
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

# !/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : 1. Langchain InMemoryChatMessageHistory.py
"""
from langchain_core.chat_history import InMemoryChatMessageHistory

# Initialize chat history
chat_history = InMemoryChatMessageHistory()

# Add a user message
chat_history.add_user_message("Hello, I'm Ling. Who are you?")
# Add an AI message
chat_history.add_ai_message("Hello, I'm ChatGPT. How can I help you?")

# Print the chat history
print(chat_history.messages)

# !/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : 2.File_Conversation_Message_History_with_Memory.py
"""
import dotenv
from langchain_community.chat_message_histories import FileChatMessageHistory
from openai import OpenAI

# Load environment variables from .env file
dotenv.load_dotenv()

# 1. Create a client and initialize memory
client = OpenAI()
chat_history = FileChatMessageHistory("./memory.txt")

# 2. Start the conversation loop
while True:
    # 3. Get user input
    query = input("Human: ")

    # 4. Check if the user wants to exit the conversation
    if query == "q":
        exit(0)

    # 5. Initiate the chat conversation
    print("AI: ", flush=True, end="")

    # System prompt for the AI with chat history context
    system_prompt = (
        "You are ChatGPT, a chatbot developed by OpenAI. "
        "You can respond to user information based on the provided context, "
        "which contains a list of conversation history between the human and you.\n\n"
        f"<context>{chat_history}</context>\n\n"
    )

    # Generate the AI's response
    response = client.chat.completions.create(
        model='gpt-3.5-turbo-16k',
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ],
        stream=True,  # Stream the response in chunks
    )

    # Collect the AI's response
    ai_content = ""
    for chunk in response:
        content = chunk.choices[0].delta.content
        if content is None:
            break
        ai_content += content
        print(content, flush=True, end="")

    # Store the conversation in chat history
    chat_history.add_user_message(query)
    chat_history.add_ai_message(ai_content)
    print("")  # Print a new line for readability
