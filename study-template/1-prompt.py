from datetime import datetime

from langchain_core.prompts import (
    PromptTemplate,
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    MessagesPlaceholder
)

# Define a prompt template
prompt_template = PromptTemplate.from_template("Tell me a cold joke about {subject}")

# Format the prompt with a specific subject
prompt_str = prompt_template.format(subject="programmers")
print(prompt_str + "\n")
print("==========\n")

# Define a chat prompt template
chat_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are a chatbot developed by OpenAI. Please respond to the user's question. The current time is {now}"),
    MessagesPlaceholder(variable_name="chat_history"),
    HumanMessagePromptTemplate.from_template("Tell me a cold joke about {subject}")
]).partial(now=datetime.now())

# Invoke the chat prompt with user input
chat_prompt_value = chat_prompt.invoke({
    "subject": "programmers",
    "chat_history": [
        ("human", "My name is Mu Xiaoke"),
        ("AIMessage", "I am ChatGPT. How can I help you?")
    ]
})

print(chat_prompt)
print(chat_prompt_value)
print("==========\n")
