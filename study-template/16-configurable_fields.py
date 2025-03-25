#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
# @File    : 1.configurable_fields.py
"""
import dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import ConfigurableField
from langchain_openai import ChatOpenAI

dotenv.load_dotenv()

# 1. Create a prompt template
prompt = PromptTemplate.from_template("Please generate a random integer less than {x}")

# 2. Create an LLM (Large Language Model) and configure the temperature parameter to be adjustable at runtime,
#    with the configuration key set as 'llm_temperature'
llm = ChatOpenAI(model="gpt-3.5-turbo-16k").configurable_fields(
    temperature=ConfigurableField(
        id="llm_temperature",
        name="LLM Temperature",
        description="The lower the temperature, the more deterministic the generated content; "
                    "the higher the temperature, the more random the generated content."
    )
)

# 3. Construct the chain application
chain = prompt | llm | StrOutputParser()

# 4. Regular invocation
content = chain.invoke({"x": 1000})
print(content)

print("===========================")

# 5. Modify the temperature to 0 for the invocation
with_config_chain = chain.with_config(configurable={"llm_temperature": 0})
content = with_config_chain.invoke({"x": 1000})
# Alternatively:
# content = chain.invoke(
#     {"x": 1000},
#     config={"configurable": {"llm_temperature": 0}}
# )
print(content)

print("===========================")

### Example 2

from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import ConfigurableField

# 1. Create a prompt template and configure it to support dynamically configurable fields
prompt = PromptTemplate.from_template("Please write a dark joke about the topic {subject}").configurable_fields(
    template=ConfigurableField(id="prompt_template"),
)

# 2. Pass configuration to modify the `prompt_template` and invoke content generation
content = prompt.invoke(
    {"subject": "programmer"},
    config={"configurable": {"prompt_template": "Please write an acrostic poem about the topic {subject}"}}
).to_string()

print(content)
