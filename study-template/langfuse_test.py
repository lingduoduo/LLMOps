import os

from dotenv import load_dotenv
from langfuse.decorators import observe
from langfuse.openai import openai  # OpenAI integration

load_dotenv()  # take environment variables from .env.

# Now these are available as environment variables
openai_api_key = os.environ.get("OPENAI_API_KEY")
langfuse_public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
langfuse_secret_key = os.environ.get("LANGFUSE_SECRET_KEY")


@observe()
def story():
    return openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a great storyteller."},
            {"role": "user", "content": "Once upon a time in a galaxy far, far away..."}
        ],
    ).choices[0].message.content


@observe()
def main():
    print(story())


main()
