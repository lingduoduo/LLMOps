from langchain_core.prompts import (
    PipelinePromptTemplate,
    PromptTemplate
)

# Define the full template
full_template = """{instruction}
{example}
{start}"""

full_prompt = PromptTemplate.from_template(full_template)

# Instruction prompt template
instruction_template = "You are simulating {person}."
instruction_prompt = PromptTemplate.from_template(instruction_template)

# Example prompt template
example_template = """Example:
Below is an interaction example
Q: {example_q}
A: {example_a}"""
example_prompt = PromptTemplate.from_template(example_template)

# Start prompt template
start_template = """Now, you are a real person. Please answer the user's question!
Q: {input}
A:"""
start_prompt = PromptTemplate.from_template(start_template)

# Define input prompts
input_prompts = [
    ("instruction", instruction_prompt),
    ("example", example_prompt),
    ("start", start_prompt)
]

# Create a pipeline prompt template
pipeline_prompt = PipelinePromptTemplate(
    final_prompt=full_prompt,
    input_prompts=input_prompts
)

# Print formatted prompt
print(pipeline_prompt.format(
    person="Ling",
    example_q="What is your favorite fruit?",
    example_a="Apple",
    input="What is your favorite phone?"
))
