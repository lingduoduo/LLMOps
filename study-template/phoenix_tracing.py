import os

import dotenv
from openai import OpenAI
from openinference.instrumentation.openai import OpenAIInstrumentor
from phoenix.otel import register

# 1. Load environment variables
dotenv.load_dotenv()

# 2. Ensure Phoenix endpoint is set
os.environ.setdefault("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006/v1/traces")

# 3. Register Phoenix tracer
tracer_provider = register(
    project_name="default",
    endpoint=os.environ["PHOENIX_COLLECTOR_ENDPOINT"],
    auto_instrument=True
)
tracer = tracer_provider.get_tracer(__name__)


# 4. Example traced function
@tracer.chain
def my_func(input: str) -> str:
    return "output"


print(my_func("input example"))

# 5. Instrument OpenAI (only once, no check needed)
OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)

# 6. Initialize OpenAI client
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("Missing OPENAI_API_KEY in environment.")
client = OpenAI(api_key=api_key)

# 7. Call OpenAI and print
response = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "Say this is a test"}],
)
print(response.choices[0].message.content)
