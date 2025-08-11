import os

import dotenv

dotenv.load_dotenv()

# Optionally set these
os.environ.setdefault("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006/v1/traces")
# os.environ.setdefault("PHOENIX_PROJECT_NAME", "default")
# Make sure OPENAI_API_KEY is set too
from phoenix.otel import register
from openinference.instrumentation.langchain import LangChainInstrumentor
from langchain_openai import ChatOpenAI
from langchain.chains import LLMMathChain
from langchain.agents import AgentType, Tool, initialize_agent
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder

# Register Phoenix tracer
tracer_provider = register(
    project_name="default",
    endpoint=os.environ["PHOENIX_COLLECTOR_ENDPOINT"],
    auto_instrument=True,
    batch=True,  # use batch processor
    verbose=True,
)
tracer = tracer_provider.get_tracer(__name__)

# Instrument LangChain
LangChainInstrumentor(tracer_provider=tracer_provider).instrument(skip_dep_check=True)

# Initialize LLM
llm = ChatOpenAI(temperature=0)

# Create math tool
llm_math = LLMMathChain.from_llm(llm=llm, verbose=True)
tools = [
    Tool(
        name="Calculator",
        func=llm_math.run,
        description="use for math questions",
    ),
]

# Build prompt and agent
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant"),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

agent_executor = initialize_agent(
    tools, llm,
    agent=AgentType.OPENAI_FUNCTIONS,
    verbose=True,
    prompt=prompt
)

# Run a sample query
response = agent_executor.invoke({"input": "What is 47 raised to the 5th power?"})
print(response)

# Additional queries
for q in [
    "What is (121 * 3) + 42?",
    "what is 3 * 3?",
    "what is 4 * 4?",
    "what is 75 * (3 + 4)?",
    "what is 23 times 87",
]:
    print("> " + q)
    resp = agent_executor.invoke({"input": q})
    print(resp)
    print("---")
