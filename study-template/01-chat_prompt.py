from datetime import datetime

from langchain_core.prompts import (
    PromptTemplate,
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    MessagesPlaceholder
)

# Define a prompt template
prompt_template = PromptTemplate.from_template("What is our 401k {subject}")

# Format the prompt with a specific subject
prompt_str = prompt_template.format(subject="Benefits")
print(prompt_str + "\n")
print("==========\n")

# Define a chat prompt template
chat_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a chatbot. Please respond to the user's question. The current time is {now}"),
    MessagesPlaceholder(variable_name="chat_history"),
    HumanMessagePromptTemplate.from_template("What is our 401k about {subject}")
]).partial(now=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

# Invoke the chat prompt with user input
chat_prompt_value = chat_prompt.invoke({
    "chat_history": [
        ("human", "My name is Ling"),
        ("ai", "I am ChatGPT. How can I help you?"),  # FIXED: Changed "AIMessage" to "ai"
    ],
    "subject": "programmers",
})

print(chat_prompt)
print(chat_prompt_value.to_string())
print("==========\n")
