# phoenix_local_agents.py

import asyncio
import os
import uuid

import dotenv
import nest_asyncio
from agents import Runner, function_tool, Agent
from phoenix.otel import register

# --- 1. Environment & Tracing Setup ---
dotenv.load_dotenv()
nest_asyncio.apply()

os.environ.setdefault("PHOENIX_SESSION_ID", f"session-{uuid.uuid4().hex[:8]}")
tracer_provider = register(
    project_name="openai-agents",
    endpoint="http://localhost:6006/v1/traces",
    auto_instrument=True,
    batch=True,
    verbose=True,
)
tracer = tracer_provider.get_tracer(__name__)


# --- 2. Agent Definition ---
@function_tool
def solve_equation(equation: str) -> str:
    return str(eval(equation))  # ⚠️ secure eval if using user input


agent = Agent(
    name="Math Solver",
    instructions="You solve math problems by evaluating them with Python.",
    tools=[solve_equation],
)


# This is our task function. It takes a question and returns the final output and the messages recorded to generate the final output.
async def solve_math_problem(dataset_row: dict):
    result = await Runner.run(agent, dataset_row.get("question"))
    return {
        "final_output": result.final_output,
        "messages": result.to_input_list(),
    }


dataset_row = {"question": "What is 15 + 28?"}

result = asyncio.run(solve_math_problem(dataset_row))
print(result)

import pandas as pd

from phoenix.evals import OpenAIModel, llm_classify


def correctness_eval(input, output):
    # Template for evaluating math problem solutions
    MATH_EVAL_TEMPLATE = """
    You are evaluating whether a math problem was solved correctly.

    [BEGIN DATA]
    ************
    [Question]: {question}
    ************
    [Response]: {response}
    [END DATA]

    Assess if the answer to the math problem is correct. First work out the correct answer yourself,
    then compare with the provided response. Consider that there may be different ways to express the same answer
    (e.g., "43" vs "The answer is 43" or "5.0" vs "5").

    Your answer must be a single word, either "correct" or "incorrect"
    """

    # Run the evaluation
    rails = ["correct", "incorrect"]
    eval_df = llm_classify(
        data=pd.DataFrame([{"question": input["question"], "response": output["final_output"]}]),
        template=MATH_EVAL_TEMPLATE,
        model=OpenAIModel(model="gpt-4.1"),
        rails=rails,
        provide_explanation=True,
    )
    label = eval_df["label"][0]
    score = 1 if label == "correct" else 0
    return score


MATH_GEN_TEMPLATE = """
You are an assistant that generates diverse math problems for testing a math solver agent.
The problems should include:

Basic Operations: Simple addition, subtraction, multiplication, division problems.
Complex Arithmetic: Problems with multiple operations and parentheses following order of operations.
Exponents and Roots: Problems involving powers, square roots, and other nth roots.
Percentages: Problems involving calculating percentages of numbers or finding percentage changes.
Fractions: Problems with addition, subtraction, multiplication, or division of fractions.
Algebra: Simple algebraic expressions that can be evaluated with specific values.
Sequences: Finding sums, products, or averages of number sequences.
Word Problems: Converting word problems into mathematical equations.

Do not include any solutions in your generated problems.

Respond with a list, one math problem per line. Do not include any numbering at the beginning of each line.
Generate 25 diverse math problems. Ensure there are no duplicate problems.
"""

import nest_asyncio

nest_asyncio.apply()
pd.set_option("display.max_colwidth", 500)

# Initialize the model
model = OpenAIModel(model="gpt-4o", max_tokens=1300)

# Generate math problems
resp = model(MATH_GEN_TEMPLATE)

# Create DataFrame
split_response = resp.strip().split("\n")
math_problems_df = pd.DataFrame(split_response, columns=["question"])
print(math_problems_df.head())

### Experiments
import uuid

unique_id = uuid.uuid4()

import pandas as pd


# Sample task and evaluator
def solve_math_problem(example):
    question = example["question"]
    # Dummy LLM call or logic (replace with real logic)
    return {"answer": eval(question.split("is")[-1])}


import uuid

unique_id = uuid.uuid4()

dataset_name = "math-questions-" + str(uuid.uuid4())[:5]


# Upload the dataset to Phoenix
# dataset = px.Client().upload_dataset(
#     dataframe=math_problems_df,
#     input_keys=["question"],
#     dataset_name=f"math-questions-{unique_id}",
# )
# print(dataset)
#
# from phoenix.experiments import run_experiment
#
# initial_experiment = run_experiment(
#     dataset,
#     task=solve_math_problem,
#     evaluators=[correctness_eval],
#     experiment_description="Solve Math Problems",
#     experiment_name=f"solve-math-questions-{str(uuid.uuid4())[:5]}",
# )

# This is our modified correctness evaluator.
def correctness_eval(input, output):
    # Template for evaluating math problem solutions
    MATH_EVAL_TEMPLATE = """
    You are evaluating whether a math problem was solved correctly.

    [BEGIN DATA]
    ************
    [Question]: {question}
    ************
    [Response]: {response}
    [END DATA]

    Assess if the answer to the math problem is correct. First work out the correct answer yourself,
    then compare with the provided response. Consider that there may be different ways to express the same answer
    (e.g., "43" vs "The answer is 43" or "5.0" vs "5").

    Your answer must be a single word, either "correct" or "incorrect"
    """

    # Run the evaluation
    rails = ["correct", "incorrect"]
    eval_df = llm_classify(
        data=pd.DataFrame([{"question": input["question"], "response": output["final_output"]}]),
        template=MATH_EVAL_TEMPLATE,
        model=OpenAIModel(model="gpt-4.1"),
        rails=rails,
        provide_explanation=True,
    )

    return eval_df


from opentelemetry.trace import StatusCode, format_span_id
import phoenix as px
from phoenix.trace import SpanEvaluations


# This is our modified task function.
async def solve_math_problem(dataset_row: dict):
    with tracer.start_as_current_span(name="agent", openinference_span_kind="agent") as agent_span:
        question = dataset_row.get("question")
        agent_span.set_input(question)
        agent_span.set_status(StatusCode.OK)

        result = await Runner.run(agent, question)
        agent_span.set_output(result.final_output)

        task_result = {
            "final_output": result.final_output,
            "messages": result.to_input_list(),
        }

        # Evaluation span for correctness
        with tracer.start_as_current_span(
                "correctness-evaluator",
                openinference_span_kind="evaluator",
        ) as eval_span:
            evaluation_result = correctness_eval(dataset_row, task_result)
            eval_span.set_attribute("eval.label", evaluation_result["label"][0])
            eval_span.set_attribute("eval.explanation", evaluation_result["explanation"][0])

        # Logging our evaluation
        span_id = format_span_id(eval_span.get_span_context().span_id)
        score = 1 if evaluation_result["label"][0] == "correct" else 0
        eval_data = {
            "span_id": span_id,
            "label": evaluation_result["label"][0],
            "score": score,
            "explanation": evaluation_result["explanation"][0],
        }
        df = pd.DataFrame([eval_data])
        px.Client().log_evaluations(
            SpanEvaluations(
                dataframe=df,
                eval_name="correctness",
            ),
        )

    return task_result


dataset_row = {"question": "What is 15 + 28?"}

result = asyncio.run(solve_math_problem(dataset_row))
print(result)
