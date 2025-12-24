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
print("--------------------------------------------------")

# !/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2024/7/13 12:34
@File    : 2.LLM_text_to_image_application.py
"""
import dotenv
from langchain_community.tools.openai_dalle_image_generation import OpenAIDALLEImageGenerationTool
from langchain_community.utilities.dalle_image_generator import DallEAPIWrapper
from langchain_openai import ChatOpenAI

dotenv.load_dotenv()

# Create a DALL·E image generation tool using the DALL·E 3 model
dalle = OpenAIDALLEImageGenerationTool(api_wrapper=DallEAPIWrapper(model="dall-e-3"))

# Create an LLM instance and bind the tool
llm = ChatOpenAI(model="gpt-4o")
llm_with_tools = llm.bind_tools([dalle], tool_choice="openai_dalle")

# Create a chain to extract tool arguments and run the tool
chain = llm_with_tools | (lambda msg: msg.tool_calls[0]["args"]) | dalle

# Invoke the chain with an English prompt
print(chain.invoke("Please draw an image of an elderly man climbing a mountain."))
