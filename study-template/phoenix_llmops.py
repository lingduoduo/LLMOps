# # Install if needed:
# # %pip install -Uqq arize-phoenix langchain langchain-openai chromadb nest_asyncio
# import os
# import uuid
#
# import dotenv
# import nest_asyncio
# # Phoenix + OpenTelemetry
# import phoenix as px
# # LangChain + OpenAI
# from langchain.chains import RetrievalQA
# from langchain.schema import Document
# from langchain.text_splitter import CharacterTextSplitter
# from langchain.vectorstores import Chroma
# from langchain_openai import ChatOpenAI
# from openinference.instrumentation import using_session
# from openinference.instrumentation.langchain import LangChainInstrumentor
# from openinference.semconv.trace import SpanAttributes
# from phoenix.otel import register
# from tqdm import tqdm
#
# # Load .env variables
# dotenv.load_dotenv()
#
# # Phoenix endpoint setup
# phoenix_endpoint = os.getenv("PHOENIX_COLLECTOR_ENDPOINT", "http://127.0.0.1:6006/v1/traces")
# os.environ["PHOENIX_COLLECTOR_ENDPOINT"] = phoenix_endpoint
#
# # --- Register Phoenix tracing ---
# tracer_provider = register(
#     project_name="default",
#     endpoint=phoenix_endpoint,
#     auto_instrument=True,
#     batch=True,
#     verbose=True,
# )
# LangChainInstrumentor().instrument(tracer_provider=tracer_provider)
# tracer = tracer_provider.get_tracer(__name__)
#
# import os
#
# os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
#
# import dotenv
#
# # Load environment variables
# dotenv.load_dotenv()
#
# from langchain_openai import OpenAIEmbeddings
#
# # --- Connect to Phoenix client ---
# client = px.Client(host=phoenix_endpoint)
#
# # --- Dummy chat inputs to simulate span ---
# SYSTEM_PROMPT = {"role": "system", "content": "You are a helpful assistant."}
# messages = [{"role": "user", "content": "Hello, what is Phoenix?"}]
# session_id = str(uuid.uuid4())
#
# try:
#     print("Phoenix session URL (self-hosted):", px.active_session().url)
#     with tracer.start_as_current_span(
#             name="agent",
#             attributes={SpanAttributes.OPENINFERENCE_SPAN_KIND: "agent"},
#     ) as span:
#         span.set_attribute(SpanAttributes.SESSION_ID, session_id)
#         span.set_attribute(SpanAttributes.INPUT_VALUE, messages[-1].get("content"))
#
#         with using_session(session_id):
#             # Simulate OpenAI chat call (Optional or replace this with actual usage)
#             response = ChatOpenAI(model="gpt-3.5-turbo").invoke(messages[-1]["content"])
#             print("Chat response:", response.content)
#
# except Exception as e:
#     print("Failed to fetch session:", e)
#
# # --- Create toy documents and embed them ---
# sample_docs = [
#     Document(page_content="You can query monitor status using the GraphQL API at /v1/graphql/monitor"),
#     Document(page_content="Delete a model using the `deleteModel` mutation in the GraphQL API"),
#     Document(page_content="Enterprise license pricing is customized. Contact Arize support."),
#     Document(page_content="Log a prediction using the Python SDK with `log_prediction(model_id=..., features=...)`")
# ]
#
# text_splitter = CharacterTextSplitter(chunk_size=300, chunk_overlap=50)
# docs = text_splitter.split_documents(sample_docs)
#
# embedding_model = OpenAIEmbeddings(model="text-embedding-ada-002")
# vectorstore = Chroma.from_documents(documents=docs, embedding=embedding_model)
# retriever = vectorstore.as_retriever()
#
# llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0)
# qa_chain = RetrievalQA.from_chain_type(llm=llm, retriever=retriever)
#
# # --- Run Queries ---
# queries = [
#     "How can I query for a monitor's status using GraphQL?",
#     "How do I delete a model?",
#     "How much does an enterprise license of Arize cost?",
#     "How do I log a prediction using the python SDK?",
# ]
#
# for query in tqdm(queries):
#     result = qa_chain.run(query)
#     print(f"\nQuery: {query}\nResponse: {result}")
#
# # --- Phoenix Evaluation ---
# from phoenix.session.evaluation import get_qa_with_reference
# from phoenix.evals import (
#     HALLUCINATION_PROMPT_TEMPLATE, HALLUCINATION_PROMPT_RAILS_MAP,
#     QA_PROMPT_TEMPLATE, QA_PROMPT_RAILS_MAP,
#     OpenAIModel, llm_classify,
# )
#
# from phoenix.trace import SpanEvaluations
#
# nest_asyncio.apply()
# queries_df = get_qa_with_reference(px.active_session())
# model = OpenAIModel(model="gpt-4o", temperature=0.0)
#
# # Hallucination Evaluation
# hallucination_eval = llm_classify(
#     data=queries_df,
#     model=model,
#     template=HALLUCINATION_PROMPT_TEMPLATE,
#     rails=list(HALLUCINATION_PROMPT_RAILS_MAP.values()),
#     provide_explanation=True,
# )
# hallucination_eval["score"] = (hallucination_eval.label == "factual").astype(int)
#
# # QA Correctness Evaluation
# qa_correctness_eval = llm_classify(
#     data=queries_df,
#     model=model,
#     template=QA_PROMPT_TEMPLATE,
#     rails=list(QA_PROMPT_RAILS_MAP.values()),
#     provide_explanation=True,
#     concurrency=4,
# )
# qa_correctness_eval["score"] = (qa_correctness_eval.label == "correct").astype(int)
#
# # Log evaluation results to Phoenix
# client.log_evaluations(
#     SpanEvaluations(eval_name="Hallucination", dataframe=hallucination_eval),
#     SpanEvaluations(eval_name="QA Correctness", dataframe=qa_correctness_eval),
# )
#
# print("Phoenix UI (Post-Evaluation):", px.active_session().url)


import dotenv
# import os
# import uuid
#
# import dotenv
# import openai
# from openinference.instrumentation import using_session
# from openinference.semconv.trace import SpanAttributes
#
# # Load .env variables
# dotenv.load_dotenv()
#
# # OpenAI client
# client = openai.Client()
#
# # Tracer
# from phoenix.otel import register
#
# # Register Phoenix tracer
# os.environ.setdefault("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006/v1/traces")
#
# tracer_provider = register(
#     project_name="default",
#     endpoint=os.environ["PHOENIX_COLLECTOR_ENDPOINT"],
#     auto_instrument=True,
#     batch=True,  # use batch processor
#     verbose=True,
# )
# tracer = tracer_provider.get_tracer(__name__)
#
# # System prompt
# SYSTEM_PROMPT = {"role": "system", "content": "You are a helpful assistant."}
#
#
# def create_session_id() -> str:
#     return str(uuid.uuid4())
#
#
# def trace_assistant(messages: list[dict], session_id: str) -> dict:
#     """Traced assistant call with OpenInference session propagation."""
#     with tracer.start_as_current_span(
#             name="agent",
#             attributes={SpanAttributes.OPENINFERENCE_SPAN_KIND: "agent"},
#     ) as span:
#         span.set_attribute(SpanAttributes.SESSION_ID, session_id)
#         span.set_attribute(SpanAttributes.INPUT_VALUE, messages[-1].get("content"))
#
#         with using_session(session_id):
#             response = client.chat.completions.create(
#                 model="gpt-3.5-turbo",
#                 messages=[SYSTEM_PROMPT] + messages,
#             ).choices[0].message
#
#         span.set_attribute(SpanAttributes.OUTPUT_VALUE, response.content)
#         return response
#
#
# if __name__ == "__main__":
#     session_id = create_session_id()
#
#     messages = [{"role": "user", "content": "hi! im bob"}]
#     response = trace_assistant(messages, session_id)
#     messages += [response, {"role": "user", "content": "what's my name?"}]
#     response = trace_assistant(messages, session_id)
#
# import os
# import uuid
#
# import dotenv
# import numpy as np
# import pandas as pd
# import phoenix as px  # Phoenix client
# from langchain.chains import RetrievalQA
# from langchain_community.retrievers import KNNRetriever
# from langchain_openai import ChatOpenAI, OpenAIEmbeddings
# from openinference.instrumentation.langchain import LangChainInstrumentor
# from phoenix.otel import register
# from tqdm import tqdm
#
# # ✅ Load env and set Phoenix tracing
# dotenv.load_dotenv()
# os.environ.setdefault("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006/v1/traces")
#
# tracer_provider = register(
#     project_name="default",
#     endpoint=os.environ["PHOENIX_COLLECTOR_ENDPOINT"],
#     auto_instrument=True,
#     batch=True,
#     verbose=True,
# )
# LangChainInstrumentor().instrument(skip_dep_check=True)
#
# # ✅ Load Embeddings and Documents
# embedding = OpenAIEmbeddings(model="text-embedding-3-small")
# texts = [
#     "Arize lets you log predictions using their Python SDK by calling `arize.log()`.",
#     "You can delete a model using the Arize UI or via API by specifying the model ID.",
#     "GraphQL allows you to query monitor status with queries like `{ monitor(id: \"123\") { status } }`.",
#     "Arize enterprise license costs vary depending on usage and support tier. Contact sales for pricing.",
# ]
# df = pd.DataFrame({
#     "text": texts,
#     "text_vector": [embedding.embed_query(t) for t in texts],
# })
# knn_retriever = KNNRetriever(
#     index=np.stack(df["text_vector"].to_list()),
#     texts=df["text"].tolist(),
#     embeddings=embedding,
# )
#
# # ✅ Setup LLM and Chain
# llm = ChatOpenAI(model_name="gpt-3.5-turbo")
# my_session = str(uuid.uuid4())
# chain = RetrievalQA.from_chain_type(
#     llm=llm,
#     chain_type="stuff",
#     retriever=knn_retriever,
#     return_source_documents=True,
#     metadata={"application_type": "question_answering"},
# )
#
# # ✅ Run Queries
# queries = [
#     "How can I query for a monitor's status using GraphQL?",
#     "How do I delete a model?",
#     "How much does an enterprise license of Arize cost?",
#     "How do I log a prediction using the python SDK?",
# ]
# for query in tqdm(queries):
#     response = chain.invoke(query)
#     print(f"\nQuery: {query}")
#     print("Answer:", response['result'])
#     print("Sources:")
#     for doc in response['source_documents']:
#         print("-", doc.page_content)
#
# # ✅ Evaluation Phase
# # Evaluation model and evaluators
# from phoenix.evals import (
#     OpenAIModel,
#     HallucinationEvaluator,
#     QAEvaluator,
#     RelevanceEvaluator,
#     run_evals,
#     SpanEvaluations,
#     DocumentEvaluations,
# )
#
# # Assume Phoenix client and model are correctly setup
# client = px.Client(host=os.environ["PHOENIX_COLLECTOR_ENDPOINT"])
#
# # Fetch logs from traces
# queries_df = get_qa_with_reference(client)
# docs_df = get_retrieved_documents(client)
#
# eval_model_name = "gpt-3.5-turbo"
# eval_model = OpenAIModel(model=eval_model_name)
# hall = HallucinationEvaluator(eval_model)
# qa = QAEvaluator(eval_model)
# rel = RelevanceEvaluator(eval_model)
#
# # Run span-based and document-based evaluations
# hall_df, qa_df = run_evals(queries_df, [hall, qa], provide_explanation=True)
# rel_df = run_evals(docs_df, [rel], provide_explanation=True)[0]
#
# # Log evaluations to Phoenix
# client.log_evaluations(
#     SpanEvaluations(eval_name="Hallucination", dataframe=hall_df),
#     SpanEvaluations(eval_name="QA Correctness", dataframe=qa_df),
#     DocumentEvaluations(eval_name="Relevance", dataframe=rel_df),
# )
#
import phoenix as px

dotenv.load_dotenv()

# Optionally set these
os.environ.setdefault("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006/v1/traces")
# os.environ.setdefault("PHOENIX_PROJECT_NAME", "default")
# Make sure OPENAI_API_KEY is set too
from phoenix.otel import register
from langchain.chains import LLMMathChain

# Register Phoenix tracer
tracer_provider = register(
    project_name="default",
    endpoint=os.environ["PHOENIX_COLLECTOR_ENDPOINT"],
    auto_instrument=True,
    batch=True,  # use batch processor
    verbose=True,
)
tracer = tracer_provider.get_tracer(__name__)

# Launch the self-hosted Phoenix app and open in browser
(session := px.launch_app()).view()
print(session)
