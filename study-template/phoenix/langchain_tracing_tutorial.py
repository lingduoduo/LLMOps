df = pd.read_parquet(
    "http://storage.googleapis.com/arize-phoenix-assets/datasets/"
    "unstructured/llm/context-retrieval/langchain/database.parquet"
)
knn_retriever = KNNRetriever(
    index=np.stack(df["text_vector"]),
    texts=df["text"].tolist(),
    embeddings=OpenAIEmbeddings(),
)
chain_type = "stuff"  # stuff, refine, map_reduce, and map_rerank
chat_model_name = "gpt-3.5-turbo"
llm = ChatOpenAI(model_name=chat_model_name)
chain = RetrievalQA.from_chain_type(
    llm=llm,
    chain_type=chain_type,
    retriever=knn_retriever,
    metadata={"application_type": "question_answering"},
)

"""Instrument LangChain"""

tracer_provider = register()
LangChainInstrumentor(tracer_provider=tracer_provider).instrument(skip_dep_check=True)

"""## 5. Run Your Query Engine and View Your Traces in Phoenix

Download a sample of queries commonly asked of the Arize documentation.
"""

url = "http://storage.googleapis.com/arize-phoenix-assets/datasets/unstructured/llm/context-retrieval/arize_docs_queries.jsonl"
queries = []
with urlopen(url) as response:
    for line in response:
        line = line.decode("utf-8").strip()
        data = json.loads(line)
        queries.append(data["query"])
queries[:10]

"""Run a few queries."""

for query in tqdm(queries[:10]):
    chain.invoke(query)

"""Check the Phoenix UI as your queries run. Your traces should appear in real time.

## 6. Export and Evaluate Your Trace Data

You can export your trace data as a pandas dataframe for further analysis and evaluation.

In this case, we will export our `retriever` spans into two separate dataframes:
- `queries_df`, in which the retrieved documents for each query are concatenated into a single column,
- `retrieved_documents_df`, in which each retrieved document is "exploded" into its own row to enable the evaluation of each query-document pair in isolation.

This will enable us to compute multiple kinds of evaluations, including:
- relevance: Are the retrieved documents grounded in the response?
- Q&A correctness: Are your application's responses grounded in the retrieved context?
- hallucinations: Is your application making up false information?
"""

queries_df = get_qa_with_reference(px.Client())
retrieved_documents_df = get_retrieved_documents(px.Client())

"""Next, define your evaluation model and your evaluators.

Evaluators are built on top of language models and prompt the LLM to assess the quality of responses, the relevance of retrieved documents, etc., and provide a quality signal even in the absence of human-labeled data. Pick an evaluator type and instantiate it with the language model you want to use to perform evaluations using our battle-tested evaluation templates.
"""

eval_model = OpenAIModel(
    model="gpt-4-turbo-preview",
)
hallucination_evaluator = HallucinationEvaluator(eval_model)
qa_correctness_evaluator = QAEvaluator(eval_model)
relevance_evaluator = RelevanceEvaluator(eval_model)

hallucination_eval_df, qa_correctness_eval_df = run_evals(
    dataframe=queries_df,
    evaluators=[hallucination_evaluator, qa_correctness_evaluator],
    provide_explanation=True,
)
relevance_eval_df = run_evals(
    dataframe=retrieved_documents_df,
    evaluators=[relevance_evaluator],
    provide_explanation=True,
)[0]

px.Client().log_evaluations(
    SpanEvaluations(eval_name="Hallucination", dataframe=hallucination_eval_df),
    SpanEvaluations(eval_name="QA Correctness", dataframe=qa_correctness_eval_df),
    DocumentEvaluations(eval_name="Relevance", dataframe=relevance_eval_df),
)

"""Your evaluations should now appear as annotations on the appropriate spans in Phoenix."""

print(f"🚀 Open the Phoenix UI if you haven't already: {session.url}")

"""## 7. Final Thoughts

LLM Traces and the accompanying OpenInference Tracing specification is designed to be a category of telemetry data that is used to understand the execution of LLMs and the surrounding application context such as retrieval from vector stores and the usage of external tools such as search engines or APIs. It lets you understand the inner workings of the individual steps your application takes wile also giving you visibility into how your system is running and performing as a whole.

LLM Evals are designed for simple, fast, and accurate LLM-based evaluations. They let you quickly benchmark the performance of your LLM application and help you identify the problematic spans of execution.

For more details on Phoenix, LLM Tracing, and LLM Evals, checkout our [documentation](https://arize.com/docs/phoenix/).
"""
