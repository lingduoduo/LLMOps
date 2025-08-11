import os
import time  # CHANGE: tiny wait to ensure spans are ingested

import dotenv
from openai import OpenAI
from phoenix.otel import register

# CHANGE: remove duplicate imports

# ---------- 1) Env & constants ----------
dotenv.load_dotenv()

PHOENIX_BASE = os.getenv("PHOENIX_BASE", "http://localhost:6006")
PHOENIX_COLLECTOR = os.getenv("PHOENIX_COLLECTOR_ENDPOINT", f"{PHOENIX_BASE}/v1/traces")
PROJECT = os.getenv("PHOENIX_PROJECT_NAME", "pydantic-evals-tutorial")
PHOENIX_API_KEY = os.getenv("PHOENIX_API_KEY")  # CHANGE: read once

tracer_provider = register(
    project_name=PROJECT,  # CHANGE: keep project consistent with query/upload
    endpoint=PHOENIX_COLLECTOR,  # CHANGE: no hard-coded duplicate
    auto_instrument=True,
    batch=True,
    verbose=True,
)
tracer = tracer_provider.get_tracer(__name__)

client = OpenAI()  # keep single client

inputs = [
    "What is the capital of France?",
    "Who wrote Romeo and Juliet?",
    "What is the largest planet in our solar system?",
]


def generate_trace(input):
    client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant. Only respond with the answer to the question as a single word or proper noun.",
            },
            {"role": "user", "content": input},
        ],
    )


for input in inputs:
    generate_trace(input)

time.sleep(1.5)  # CHANGE: brief pause so spans show up before querying
#
# query = SpanQuery().select(
#     input="llm.input_messages",
#     output="llm.output_messages",
# )
#
# # The Phoenix Client can take this query and return the dataframe.
# phoenix_client = px.Client(endpoint=PHOENIX_BASE, api_key=PHOENIX_API_KEY)  # CHANGE: reuse base+key
# spans = phoenix_client.query_spans(query, project_name=PROJECT)
#
#
# # CHANGE: safer extraction (same shape as your lambdas, just robust)
# def _last_user_content(msgs):
#     try:
#         for m in reversed(msgs):
#             if m.get("message", {}).get("role") == "user":
#                 return m["message"].get("content")
#     except Exception:
#         return None
#
#
# def _first_assistant_content(msgs):
#     try:
#         for m in msgs:
#             if m.get("message", {}).get("role") == "assistant":
#                 return m["message"].get("content")
#     except Exception:
#         return None
#
#
# spans["input"] = spans["input"].apply(_last_user_content)  # CHANGE
# spans["output"] = spans["output"].apply(_first_assistant_content)  # CHANGE
# spans = spans.dropna(subset=["input", "output"]).reset_index(drop=True)  # CHANGE: avoid None rows
# spans.head()
#
# cases = [
#     Case(
#         name="capital of France", inputs="What is the capital of France?", expected_output="Paris"
#     ),
#     Case(
#         name="author of Romeo and Juliet",
#         inputs="Who wrote Romeo and Juliet?",
#         expected_output="William Shakespeare",
#     ),
#     Case(
#         name="largest planet",
#         inputs="What is the largest planet in our solar system?",
#         expected_output="Jupiter",
#     ),
# ]
#
#
# # Setup LLM task, Evaluator, and Dataset for Pydantic
# async def task(input: str) -> str:
#     # CHANGE: avoid per-call .values[0] crash if missing
#     row = spans.loc[spans["input"] == input, "output"]
#     return row.iloc[0] if len(row) else ""
#
#
# class MatchesExpectedOutput(Evaluator[str, str]):
#     def evaluate(self, ctx: EvaluatorContext[str, str]) -> float:
#         # CHANGE: normalize whitespace/case a bit; still returns bool/float as expected
#         is_correct = ctx.expected_output.strip() == (ctx.output or "").strip()
#         return bool(is_correct)
#
#
# dataset = Dataset(
#     cases=cases,
#     evaluators=[MatchesExpectedOutput()],
# )
#
# report = dataset.evaluate_sync(task)
# print(report)
#
#
# # Redefine Eval to be LLM-powered or Semantic
# class FuzzyMatchesOutput(Evaluator[str, str]):
#     def evaluate(self, ctx: EvaluatorContext[str, str]) -> float:
#         from difflib import SequenceMatcher
#         a = (ctx.expected_output or "").strip().casefold()  # CHANGE: robust
#         b = (ctx.output or "").strip().casefold()
#         return SequenceMatcher(None, a, b).ratio() > 0.8
#
#
# dataset.add_evaluator(FuzzyMatchesOutput())
# from pydantic_evals.evaluators import LLMJudge
#
# dataset.add_evaluator(
#     LLMJudge(
#         rubric="Output and Expected Output should represent the same answer, even if the text doesn't match exactly",
#         include_input=True,
#         model="openai:gpt-4o-mini",
#     ),
# )
# report = dataset.evaluate_sync(task)
# print(report)
#
# # Upload Labels to Phoenix
# results = report.model_dump()
# # Create a dataframe for each eval
# meo_spans = spans.copy()
# fuzzy_label_spans = spans.copy()
# llm_label_spans = spans.copy()
#
# # CHANGE: init as booleans (avoid str(True)/str(False) bug)
# meo_spans["label"] = False
# fuzzy_label_spans["label"] = False
# llm_label_spans["label"] = False
#
# for case in results.get("cases", []):
#     meo_label = case.get("assertions", {}).get("MatchesExpectedOutput", {}).get("value")
#     fuzzy_label = case.get("assertions", {}).get("FuzzyMatchesOutput", {}).get("value")
#     llm_label = case.get("assertions", {}).get("LLMJudge", {}).get("value")
#
#     input_val = case.get("inputs")
#
#     # CHANGE: each df filters on itself; fix copy/paste bug on fuzzy line
#     meo_spans.loc[meo_spans["input"] == input_val, "label"] = bool(meo_label)
#     fuzzy_label_spans.loc[fuzzy_label_spans["input"] == input_val, "label"] = bool(fuzzy_label)
#     llm_label_spans.loc[llm_label_spans["input"] == input_val, "label"] = bool(llm_label)
#
# # Phoenix can also take in a numeric score for each row which it uses to calculate overall metrics
# meo_spans["score"] = meo_spans["label"].astype(int)  # CHANGE: 0/1 correctly
# fuzzy_label_spans["score"] = fuzzy_label_spans["label"].astype(int)
# llm_label_spans["score"] = llm_label_spans["label"].astype(int)
#
# print(meo_spans.head())
#
# # Upload your data to Phoenix:
# # CHANGE: reuse same client & pass project_name to be explicit
# phoenix_client.log_evaluations(
#     SpanEvaluations(
#         dataframe=meo_spans,
#         eval_name="Direct Match Eval",
#         project_name=PROJECT,  # CHANGE
#     ),
# )
# phoenix_client.log_evaluations(
#     SpanEvaluations(
#         dataframe=fuzzy_label_spans,
#         eval_name="Fuzzy Match Eval",
#         project_name=PROJECT,  # CHANGE
#     ),
# )
# phoenix_client.log_evaluations(
#     SpanEvaluations(
#         dataframe=llm_label_spans,
#         eval_name="LLM Match Eval",
#         project_name=PROJECT,  # CHANGE
#     ),
# )
