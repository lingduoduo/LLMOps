#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2024/7/13 11:00
@File    : 1.multimodal_llm_tool_call.py
"""

import base64

import dotenv
import httpx
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

dotenv.load_dotenv()

# 1. Construct prompt
prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "Describe the image provided"),
        ("user", [{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,{image_data}"}, }],
         ),
    ]
)

# 2. Build the LLM and bind the tool
llm = ChatOpenAI(model="gpt-4o")
chain = prompt | llm

# 3. Create and run the chain

image_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg"
image_data = base64.b64encode(httpx.get(image_url).content).decode("utf-8")

response = chain.invoke({"image_data": image_data})
print(response.content)
