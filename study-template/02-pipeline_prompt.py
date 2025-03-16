from langchain_core.prompts import ChatPromptTemplate

# Define a system prompt template
system_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a chatbot developed by OpenAI. Please respond to the user's questions. My name is {username}.")
])

# Define a human prompt template
human_prompt = ChatPromptTemplate.from_messages([
    ("human", "{query}")
])

# Combine both prompts
prompt = system_prompt + human_prompt

# Print the prompts
print(prompt)
print(prompt.format(username="Alice", query="What is the weather today?"))
