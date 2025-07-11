Langfuse is building the **open source LLM Engineering Platform**. We are building *the* platform to observe and improve LLM applications.

- **Full context capture:** Track the complete execution flow including API calls, context, prompts, parallelism and more
- **Cost monitoring:** Track model usage and costs across your application
- **Quality insights:** Collect user feedback and identify low-quality outputs
- **Dataset creation:** Build high-quality datasets for fine-tuning and testing
- **Root cause analysis:** Quickly identify and debug issues in complex LLM applications



![Screenshot 2025-07-03 at 1.40.05 PM](/Users/huanglin/Library/CloudStorage/OneDrive-AutomaticDataProcessingInc/Desktop/Screenshot 2025-07-03 at 1.40.05 PM.png)

Two versions:

- Langfuse cloud
- Self Host - https://langfuse.com/self-hosting/v2

**Demo**

- Core Platform
- LLM-as-Judge
- Playground
- Prompt Engineering
- Annotation / Data Labeling

![Screenshot 2025-07-03 at 2.22.37 PM](/Users/huanglin/Library/CloudStorage/OneDrive-AutomaticDataProcessingInc/Desktop/Screenshot 2025-07-03 at 2.22.37 PM.png)



## Core Features

**Langfuse Dashboard**

With langfuse dashboard you can see all important metrics to monitor your LLM application that includes overall volume usage by model or token types, cost breakdowns by user, latency distributions and quality metrics tracing is at the very core of platform.

**Tracing**

It will capture all the interactions with your LLM-application. For e.g. in a typical RAG application you will see traces of the interaction and length view which highlights which documents actually went into producing the answer as they were fetched from our corpus, how the embedding workflow worked and then the context and to understand how it reached the response.

- Log traces
- Lowest level transparency 
- Understand cost and latency

**Prompts**

In simple layman terms, Langfuse prompt management is a Prompt Content Management System.  Langfuse prompt management helps to version edit prompt to production and instantly roll back prompts, thereby everyone on the team can contribute and see which prompts are used without touching the code- base. Langfuse prompts are linked to traces as we can see which prompt was used when a specific good or bad trace has happened going back to the
prompt.

- Vision control and deploy
- Collaborate on prompts
- Test prompts and models.

**Evals**

Langfuse interface evaluation is super important to understand how the LLM-powered application actually works. You can use different evaluation methods for production applications, you can capture user-feedback and any comments via the SDKs. You can configure Langfuse to run element, judge evaluators on all new created traces, these evaluators can run on the whole trace input and output or also evaluate a section of the trace, etc.

- Measure output quality
- Monitor production health
- Test changes in development

**Datasets and Experiments**

Simply, datasets can be used in development to test your LLM applications. A data set is a test set of example inputs and outputs. Langfuse datasets & experiments can be used to test which of our prompt versions is actually better to make a good decision before moving them to production. Say if there are some new ideas that you want to test every week and you need to do prompt iteration, a new model checkpoint or a new agent strategy or a new retrieval method or change configuration etc this is where experimentation comes into play.

**Playground**

With the LLM playground, you can now test and iterate your prompts directly in Langfuse. Either start from scratch or jump into the playground.



**Use cases**

Embedding model

Intent Classification

Hybrid Search

Reranker

Parameter Extraction





https://confluence.es.ad.adp.com/spaces/Sfe/pages/758450212/1NAS+Team+Structure

Question to get team email.

https://ajay-arunachalam08.medium.com/exploring-langfuse-an-open-source-llm-engineering-platform-38cf5fe746e6

sk-lf-933804bd-1a74-429f-917d-954359d4b1aa

pk-lf-49583f62-2dee-4898-a21a-099d0ee5dcf9

http://localhost:3000



**LLM Models**

our dashboards if you wanna bookmark somewhere -

Prod: https://adp-cloud.splunkcloud.com/en-US/app/lifion/lyric_ai_gateway_metrics

Non-Prod: https://adpdev.splunkcloud.com/en-US/app/lifion/lyric_ai_gateway_metrics



**7/8/2025**

**Dataset Get Started**

https://langfuse.com/self-hosting/v2

https://github.com/orgs/langfuse/discussions/3824 - unable to find all 



Step into the world of LLMs with this practical guide that takes you from the fundamentals to deploying advanced applications using LLMOps best practices Key Features Build and refine LLMs step by step, covering data preparation, RAG, and fine-tuning Learn essential skills for deploying and monitoring LLMs, ensuring optimal performance in production Utilize preference alignment, evaluation, and inference optimization to enhance performance and adaptability of your LLM applications.



Prompt engineering is a crucial aspect of generative AI, but it can be difficult to make the leap from writing simple prompts to using generative AI to build a minimum viable product (MVP). Equally challenging can be determining which tools are best for the job. This head-to-head competition harnesses the power of generative AI and offers guidance on what tools and techniques can help you get from prompt to product.



Python Ecosystem

MLOps and LLMOps tooling

Databases for storing unstructured and vector data



## Prompt monitoring tools

Langfuse (open source, [https://langfuse.com](https://langfuse.com/))

LangSmith (not open source, https://www.langchain.com/langsmith)

Galileo (not open source, [rungalileo.io](https://rungalileo.io/))

Opik (open source, https://github.com/comet-ml/opik.)



## Vector Database

Milvus

Solr

Redis

Qdrant: vector database

Weaviate

Pinecone

Chroma

pgvector (a PostgreSQL plugin for vector indexes)

Step into the world of LLMs with this practical guide that takes you from the fundamentals to deploying advanced applications using LLMOps best practices Key Features Build and refine LLMs step by step, covering data preparation, RAG, and fine-tuning Learn essential skills for deploying and monitoring LLMs, ensuring optimal performance in production Utilize preference alignment, evaluation, and inference optimization to enhance performance and adaptability of your LLM applications.

Prompt engineering is a crucial aspect of generative AI, but it can be difficult to make the leap from writing simple prompts to using generative AI to build a minimum viable product (MVP). Equally challenging can be determining which tools are best for the job. This head-to-head competition harnesses the power of generative AI and offers guidance on what tools and techniques can help you get from prompt to product.
