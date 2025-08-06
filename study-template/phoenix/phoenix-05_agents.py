import os
import pandas as pd
import nest_asyncio
from uuid import uuid1
from getpass import getpass

import openai
import phoenix as px
from phoenix.otel import register
from openinference.instrumentation.openai import OpenAIInstrumentor
from phoenix.evals import OpenAIModel, llm_classify
from phoenix.experiments import run_experiment
from phoenix.experiments.types import EvaluationResult

# === Setup ===
nest_asyncio.apply()

# API Keys
openai_api_key = os.getenv("OPENAI_API_KEY") or getpass("🔑 Enter your OpenAI API key: ")
os.environ["OPENAI_API_KEY"] = openai_api_key
PHOENIX_API_KEY = getpass("Enter your Phoenix API Key")
os.environ["PHOENIX_CLIENT_HEADERS"] = f"api_key={PHOENIX_API_KEY}"
os.environ["PHOENIX_COLLECTOR_ENDPOINT"] = "https://app.phoenix.arize.com"

# Phoenix Tracer
tracer_provider = register(endpoint=os.environ["PHOENIX_COLLECTOR_ENDPOINT"])
OpenAIInstrumentor().uninstrument()
OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)

# === Tool Definitions ===
tools = [
    {"type": "function", "function": {"name": "product_comparison", "description": "Compare features of two products.", "parameters": {"type": "object", "properties": {"product_a_id": {"type": "string"}, "product_b_id": {"type": "string"}}, "required": ["product_a_id", "product_b_id"]}}},
    {"type": "function", "function": {"name": "product_search", "description": "Search for products based on criteria.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "category": {"type": "string"}, "min_price": {"type": "number", "default": 0}, "max_price": {"type": "number"}, "page": {"type": "integer", "default": 1}, "page_size": {"type": "integer", "default": 20}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "customer_support", "description": "Get contact info for customer support.", "parameters": {"type": "object", "properties": {"issue_type": {"type": "string"}}, "required": ["issue_type"]}}},
    {"type": "function", "function": {"name": "track_package", "description": "Track the status of a package.", "parameters": {"type": "object", "properties": {"tracking_number": {"type": "integer"}}, "required": ["tracking_number"]}}},
    {"type": "function", "function": {"name": "product_details", "description": "Get product details.", "parameters": {"type": "object", "properties": {"product_id": {"type": "string"}}, "required": ["product_id"]}}},
    {"type": "function", "function": {"name": "apply_discount_code", "description": "Apply a discount code.", "parameters": {"type": "object", "properties": {"order_id": {"type": "integer"}, "discount_code": {"type": "string"}}, "required": ["order_id", "discount_code"]}}},
]

# === Prompt Runner ===
def run_prompt(input):
    client = openai.Client()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        tools=tools,
        tool_choice="auto",
        messages=[{"role": "system", "content": " "}, {"role": "user", "content": input}],
    )
    msg = response.choices[0].message
    return msg.content or msg.tool_calls or ""

# === Dataset Generation ===
GEN_TEMPLATE = """
You are an assistant that generates complex customer service questions...
Generate 25 questions. One per line. No numbering.
"""
model = OpenAIModel(model="gpt-4o", max_tokens=1300)
questions_df = pd.DataFrame(model(GEN_TEMPLATE).strip().split("\n"), columns=["question"])

# === Agent Execution ===
questions_df["response"] = questions_df["question"].apply(run_prompt).astype(str)

# === Evaluation Templates ===
ROUTER_EVAL_TEMPLATE = "..."
FUNCTION_SELECTION_EVAL_TEMPLATE = "..."
PARAMETER_EXTRACTION_EVAL_TEMPLATE = "..."

# === Evaluations ===
rails = ["incorrect", "correct"]
router_eval_df = llm_classify(questions_df, ROUTER_EVAL_TEMPLATE, model, rails, True, True, concurrency=4)
function_selection_eval_df = llm_classify(questions_df, FUNCTION_SELECTION_EVAL_TEMPLATE, model, rails, True, True, concurrency=4)
parameter_extraction_eval_df = llm_classify(questions_df, PARAMETER_EXTRACTION_EVAL_TEMPLATE, model, rails, True, True, concurrency=4)

# === Experiment Creation ===
client = px.Client()
dataset = client.upload_dataset(questions_df, dataset_name=f"agents-cookbook-{uuid1()}", input_keys=["question"])

# === Evaluation Functions ===
def generic_eval(input, output, prompt):
    df = pd.DataFrame({"question": [str(input["question")]], "response": [str(output)]})
    eval_df = llm_classify(df, prompt, model, rails, provide_explanation=True)
    label, explanation = eval_df["label"][0], eval_df["explanation"][0]
    return EvaluationResult(score=int(label == rails[1]), label=label, explanation=explanation)

def routing_eval(input, output): return generic_eval(input, output, ROUTER_EVAL_TEMPLATE)
def function_call_eval(input, output): return generic_eval(input, output, FUNCTION_SELECTION_EVAL_TEMPLATE)
def parameter_extraction_eval(input, output): return generic_eval(input, output, PARAMETER_EXTRACTION_EVAL_TEMPLATE)

experiment = run_experiment(
    dataset=dataset,
    task=lambda row: run_prompt(row["question"]),
    evaluators=[routing_eval, function_call_eval, parameter_extraction_eval],
    experiment_name="agents-cookbook",
)
