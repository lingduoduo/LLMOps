# Observing Applications Using Traces for LLM Systems

## Introduction

Modern LLM-powered applications orchestrate a complex interplay of model calls, data retrieval, and auxiliary tools across multiple components. To gain visibility into how these distributed systems operate, observability, or understanding what’s happening under the hood, relies on distributed tracing. Each incoming request is captured as a *trace*, which is composed of ordered *spans*. Each span records crucial metadata: timing, inputs and outputs, and contextual tags.

**Phoenix**, an open-source AI observability platform by Arize AI, extends this architecture with first-class, vendor-agnostic tracing capabilities backed by OTel. It supports automatic instrumentation for frameworks such as LangChain, LlamaIndex, and SDKs including OpenAI, AWS Bedrock, with language support across Python, JavaScript, and etc.



------

## What Traces and Spans Capture

Phoenix’s tracing capabilities give you detailed insights into every stage of your LLM workflow:

- **Application Latency**: Locate slowdowns in model calls, retrieval steps, or embedding generation to improve responsiveness. [Amazon Web Services, Inc.+7Arize AI+7Medium+7](https://arize.com/docs/phoenix/tracing/llm-traces?utm_source=chatgpt.com)
- **Token Usage**: Analyze token consumption per request, enabling cost management and efficiency tuning. [llmmodels.org+8Arize AI+8Medium+8](https://arize.com/docs/phoenix/tracing/llm-traces?utm_source=chatgpt.com)
- **Runtime Exceptions**: Detect and investigate errors—or even rate-limiting events—ensuring robust error handling. [LinkedIn+4Arize AI+4Medium+4](https://arize.com/docs/phoenix/tracing/llm-traces?utm_source=chatgpt.com)
- **Retrieved Documents**: Examine documents returned during retrieval steps, including ranking and scoring, to troubleshoot relevance and retrieval behavior. [Arize AI+9Arize AI+9Medium+9](https://arize.com/docs/phoenix/tracing/llm-traces?utm_source=chatgpt.com)
- **Embeddings**: Inspect the embedding text and model used, helping you validate and refine embedding strategies. [Arize AI+1](https://arize.com/docs/phoenix/tracing/llm-traces?utm_source=chatgpt.com)
- **LLM Parameters**: Track invocation settings like temperature and system prompts for better debugging and configuration. [Arize AI+5Arize AI+5Amazon Web Services, Inc.+5](https://arize.com/docs/phoenix/tracing/llm-traces?utm_source=chatgpt.com)
- **Prompt Templates**: Discover the prompt templates and variable values applied during generation—essential for fine-tuning prompts. [llmmodels.org+5Arize AI+5Amazon Web Services, Inc.+5](https://arize.com/docs/phoenix/tracing/llm-traces?utm_source=chatgpt.com)
- **Tool Descriptions**: View metadata, descriptions, and function signatures of tools accessible to your LLM, improving observability over agent capabilities. [YouTube+11Arize AI+11Amazon Web Services, Inc.+11](https://arize.com/docs/phoenix/tracing/llm-traces?utm_source=chatgpt.com)
- **LLM Function Calls**: For LLMs that support function calling (like OpenAI), trace function selection and input messages to debug complex interactions. [Arize AI+1](https://arize.com/docs/phoenix/tracing/llm-traces?utm_source=chatgpt.com)

------

## Customize Tracing

Tracing can be customized by defining spans around specific application logic and enriching them with **metadata**, such as custom attributes, user IDs, session IDs, or prompt templates. In addition, **tags** can be applied to classify runs or group related traces, making it easier to analyze performance, compare experiments, and track behavior across sessions.

After connecting your application to Phoenix, tracing can be enabled in three main ways:

1. **Phoenix Decorators**: wrap functions or components for selective tracing.
2. **OpenInference Auto-Instrumentors** : automatically capture spans for supported libraries.
3. **Base OpenTelemetry APIs**: create fully customized spans when finer control is required.

Phoenix OpenAIInstrumentor provides auto-instrumentation that emits fully OTel-compatible LLM spans, including prompt inputs and model outputs. It works with OpenAI and Azure OpenAI and can export to any OTEL backend (e.g., Phoenix, LangChain, Elastic).

Phoenix OpenTelemetry provides an open, vendor-neutral foundation for generating and exporting these telemetry signals. On top of this, LLM-specific observability frameworks like those following the OpenInference conventions, introduces a structured taxonomy of span kinds tailored to AI workflows, allowing observability systems to capture the unique execution patterns of LLM applications. Beyond generic spans, common categories such as **Agent, Chain, Tool, LLM, Retriever, Reranker, and Embedding** align naturally with how modern AI systems route requests, call external services, retrieve data, and generate responses. For instance, an **LLM span** captures the full lifecycle of a model call, inputs, parameters, and outputs, while a **Chain span** represents a sequence of steps or the connective logic between them. A **Tool span** records the execution of external APIs or functions invoked by the LLM, whereas an **Agent span** serves as the orchestration root, encapsulating the entire run of an agent-driven workflow. Together, these span kinds nest hierarchically to reflect the real execution structure of an LLM-powered application, making complex AI pipelines more transparent, debuggable, and measurable.

### Tracking custom spans

As an example, consider tracing a **hybrid search pipeline** where embeddings are generated using an OpenAI model, documents are retrieved from a Redis Vector Store, and results are reranked with an AWS Bedrock model. In such workflows, spans can be designed to capture each critical stage: a **sparse retrieval span** for BM25 or keyword lookups, a **dense embedding span** recording model IDs and vector dimensions, a **vector search span** for dense retrieval results, a **hybrid aggregation span** to log weighting strategies (e.g., hybrid alpha), and a **reranker span** for final scoring and ranking. Hybrid search—fusing sparse and dense methods—is essential for robust LLM-powered retrieval, and by instrumenting each step with Phoenix and OpenTelemetry, teams gain fine-grained visibility into performance bottlenecks, retrieval quality, parameter sensitivities, and potential failures, benefiting both research and operations.

###  Tracking user sessions

  In addition to tracing individual responses, Phoenix supports **sessions**, which represent a sequence of related traces tied together under a single interaction, such as a multi-turn conversation or user thread. Each model response is still captured as its own trace, but by assigning them to the same session, the system provides visibility into the flow of the entire exchange.

Sessions allow practitioners to connect multiple traces into a coherent dialogue or workflow, navigate conversation history through the **Sessions** tab with recent activity and analytics, and search interactions by message content to locate specific exchanges or investigate user behaviors. This session-level perspective moves beyond isolated traces, enabling richer evaluation of user experience, continuity of context, and overall conversational performance in LLM applicationsespecially valuable when analyzing **function calls**, where accurate parameter extraction across turns is critical for reliable execution.

### Integration with LangChain

LangChain is a powerful high-level framework that enables developers to build LLM-powered applications with just a few lines of code. However, this abstraction often conceals the underlying processes, making it difficult to debug issues, optimize performance, or manage costs. Arize Phoenix addresses these challenges by providing observability across every step (or span) of the pipeline, from retrieval through to LLM responses. By exposing spans with detailed information on latency, token usage, retrieval quality, and other key metrics, Phoenix makes it possible to identify bottlenecks, inefficiencies, and even hallucinations with clarity.

In this example, you will instrument a LangChain-based retrieval-augmented generation (RAG) pipeline with Phoenix. The workflow begins with building a simple Q&A application over the Arize documentation, then capturing trace data in the OpenInference format using Phoenix and OpenTelemetry. You will then explore the trace structure within Phoenix to uncover latency bottlenecks, token-intensive spans, and cost drivers, before exporting the data as a pandas DataFrame and applying LLM-driven evaluations to measure and refine the performance of your RAG chain.

Evaluation serves as the foundation for assessing the accuracy and reliability of the application once it has been instrumented with Phoenix. While inspecting individual queries can provide some insight, this approach quickly becomes unsustainable as the number of edge cases grows. Phoenix enables a more systematic and scalable solution by supporting a wide range of automated evaluation metrics—covering retrieval effectiveness (such as precision@k, nDCG, and hit rate) as well as response quality (such as QA correctness, hallucination detection, and toxicity analysis). Because these evaluations are tied directly to trace data and powered by reusable LLM-based evaluators, they highlight problematic spans for deeper analysis while also allowing results to be exported for dataframe-based or LLM-assisted evaluation workflows. In doing so, Phoenix turns observability into actionable insight, giving you the ability to continuously measure, diagnose, and improve the performance of your RAG system.


