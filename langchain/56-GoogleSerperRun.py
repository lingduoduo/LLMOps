import dotenv
from langchain_community.tools import GoogleSerperRun
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_core.pydantic_v1 import BaseModel, Field

dotenv.load_dotenv()


class GoogleSerperArgsSchema(BaseModel):
    query: str = Field(description="Query string to perform Google search")


google_serper = GoogleSerperRun(
    name="google_serper",
    description=(
        "A low-cost Google search API."
        "Use this tool when you need to answer questions about current events."
        "The input to this tool is a search query string."
    ),
    args_schema=GoogleSerperArgsSchema,
    api_wrapper=GoogleSerperAPIWrapper(),
)

print(google_serper.invoke("What is the world record for marathon?"))
