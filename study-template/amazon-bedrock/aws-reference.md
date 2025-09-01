### Setup AWS CLI

```
curl "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o "AWSCLIV2.pkg"
sudo installer -pkg AWSCLIV2.pkg -target /

aws configure
aws configure list
```

Here are several **hands-on workshop and evaluation notebook examples** that showcase how to create, evaluate, and iterate on Amazon Bedrock Agents. These can serve as excellent references for building your own evaluation notebooks:

------
AWS CLI settings can come from multiple places, listed here in descending priority:

- Command-line flags (e.g., --profile, --region)
- Environment variables
- Configuration (~/.aws/config)
- Credentials file (~/.aws/credentials)

------
## 1. AWS-hosted Bedrock Workshop (Agents-focused)

**Source**: *amazon-bedrock-workshop* repository

https://github.com/aws-samples/amazon-bedrock-workshop?utm_source=chatgpt.com

 This official workshop series includes lab modules built as notebooks, geared toward developers:

- **Lab 05 – Agents**: Walks you through building practical agents such as a customer service agent or an insurance claims agent.
   [aws-samples.github.io+9GitHub+9docs.ragas.io+9](https://github.com/aws-samples/amazon-bedrock-workshop?utm_source=chatgpt.com)

You can clone this repo and use Lab 05 as your starting point for an evaluation notebook:

```
git clone https://github.com/aws-samples/amazon-bedrock-workshop.git
cd amazon-bedrock-workshop/05_Agents
```

You’ll find guided steps and code snippets to get agents up and running — great for building evaluation examples.

------

## Build Real world End-to-End AI-Agents using AWS-Bedrock

https://github.com/PacktPublishing/Build-Real-world-End-to-End-AI-Agents-using-AWS-Bedrock


## 2. Open Source Bedrock Agent Evaluation Framework

**Source**: *open-source-bedrock-agent-evaluation* repository

https://github.com/aws-samples/open-source-bedrock-agent-evaluation?utm_source=chatgpt.com This evaluation framework is designed for:

- **Evaluating agents** using techniques like LLM-as-a-judge, RAG, and Text‑to‑SQL metrics.
- **Visualizing results** with dashboards and traces through integration with **Langfuse**.
   [GitHub+3GitHub+3Amazon Web Services, Inc.+3](https://github.com/aws-samples/open-source-bedrock-agent-evaluation?utm_source=chatgpt.com)

### Key features:

- Supports evaluating your **own Bedrock Agent** or sample agents.
- Works with custom datasets or provided examples.
- Uses metrics like **chain-of-thought success**, **RAG faithfulness**, and **SQL correctness**.
- **Langfuse dashboards** offer detailed agent trace visualization and comparisons.
   [aws-samples.github.io+14GitHub+14GitHub+14](https://github.com/aws-samples/open-source-bedrock-agent-evaluation?utm_source=chatgpt.com)[AWS Documentation+1](https://docs.aws.amazon.com/bedrock/latest/userguide/service_code_examples_bedrock-agent_basics.html?utm_source=chatgpt.com)

This is perfect for an evaluation notebook structured around quantitative metrics and trace-based insights.

------

## 3. Ragas-based Evaluation Notebook: Restaurant Agent

**Source**: Ragas documentation
 This notebook demonstrates a **complete evaluation pipeline** using Ragas for:

https://docs.ragas.io/en/stable/howtos/integrations/amazon_bedrock/?utm_source=chatgpt.com

- A **restaurant agent** handling menu queries and table bookings.
- Steps include building the agent, defining evaluation metrics, running the evaluation, and cleaning up.
   [docs.ragas.io+1](https://docs.ragas.io/en/stable/howtos/integrations/amazon_bedrock/?utm_source=chatgpt.com)

The practical structure makes this ideal for a self-contained evaluation notebook showcasing how to tie together agent creation and performance assessment.

------

## 4. Amazon Bedrock Agent Samples (Hands-On Examples)

**Source**: *amazon-bedrock-agent-samples* repository
 While not focused exclusively on evaluation, this repo contains:

https://github.com/aws-samples/open-source-bedrock-agent-evaluation?utm_source=chatgpt.com

- **Notebooks and code samples** demonstrating diverse agent patterns including inline agents, multi-agent collaboration, guardrails, knowledge bases, and integration with action groups.
   [aws-samples.github.io+7GitHub+7docs.ragas.io+7](https://github.com/aws-samples/open-source-bedrock-agent-evaluation?utm_source=chatgpt.com)[docs.ragas.io+4GitHub+4aws-samples.github.io+4](https://github.com/awslabs/amazon-bedrock-agent-samples?utm_source=chatgpt.com)

You can repurpose any of these agent examples into an evaluation notebook by adding evaluation logic (e.g., Ragas or LLM-as-a-judge), making them accessible templates.

------

### Summary Table

| Origin / Source                           | Focus                                  | Best Use Case                                                |
| ----------------------------------------- | -------------------------------------- | ------------------------------------------------------------ |
| Workshop Lab 05 (amazon-bedrock-workshop) | Building agents hands-on               | Ideal for crafting evaluation notebooks starting with setup  |
| Bedrock Agent Evaluation Framework        | Metrics-driven evaluation via Langfuse | Best for deep metrics, multi-turn evaluation, dashboarding   |
| Ragas Notebook (restaurant agent)         | Agent build + evaluation sample        | Great self-contained example to emulate in your notebook     |
| Agent Samples Repo (code examples)        | Agent variety & features demonstration | Useful bases—combine with evaluation logic for full notebooks |

------

## How to Build Your Evaluation Notebook

1. **Kick off with agent creation**: Use samples from the workshop or agent-samples repo to define your agent (e.g. restaurant agent, insurance agent, or inline agent).
2. **Define evaluation strategy**:
   - Use **Ragas** for robust metrics like faithfulness, relevancy, and semantic similarity.
   - Apply **LLM-as-a-judge** (chain-of-thought, instruction-following).
   - Compare with ground truth using Text-to-SQL or RAG metrics if applicable.
3. **Run evaluation**:
   - Fly through agent evaluation using the Ragas notebook as a blueprint.
   - Or leverage the Agent Evaluation Framework to integrate Langfuse visual dashboards.
4. **Visualize and analyze**:
   - Visualize trace outputs, scores, costs, and token-level details in Langfuse dashboards.
   - Use reporting to guide iteration on agent behavior and configuration.
5. **Cleanup**:
   - Make sure to include notebook steps to delete created AWS resources (agents, KBs, Lambda, DynamoDB etc.) per best practice.

------

## Sample Notebook Outline

```
# Bedrock Agent Evaluation Notebook

## 1. Setup
- Install dependencies (boto3, ragas, langfuse SDKs)
- Configure AWS credentials and Langfuse (if used)

## 2. Agent Creation
- Define and deploy a Bedrock Agent (e.g. inline or RAG agent)
- Include knowledge bases or action groups if needed

## 3. Dataset & Metrics
- Load evaluation dataset (e.g. restaurant QA, SQL questions)
- Define Ragas metric functions or LLM-judge prompts

## 4. Evaluation Execution
- Evaluate agent using Ragas or LLM-judge loop
- Capture traces and outputs

## 5. Visualization (optional)
- Send evaluation data to Langfuse
- Display dashboard snapshots or summaries

## 6. Results Summary
- Present metric tabulation: accuracy, faithfulness, chain-of-thought scores

## 7. Cleanup
- Delete agents, knowledge bases, policies, and other resources
```

| **Dataset Management**  | A PostGreSQL database is used as storage for dataset. A dataset can be built from traces (logs). The evaluation can be run either from Phoenix dashboard or from custom code using Phoenix SDK APIs. | AWS S3 is used as storage for dataset. If the evaluation is to be run with Bedrock dashboard, then the dataset must contains fields as per specifications. If the evaluation is to be run with custom code, then the dataset can contain any free structure. |
| ----------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| **Prompt Optimisation** | Prompt optimisation is an external task in Phoenix. Phoenix helps with process of evaluating the performance of different versions of a prompt; but it does not provide the optimised prompt itself. User should use tools like DSPy or techniques like gradient optimisation to improve prompt, and then use Phoenix to evaluate and compare the new prompt with earlier versions. | Bedrock uses AI to optimise prompts. On click of a button, it reads existing prompt, and uses AI to analyse and generate a new prompt. The new prompt can then be tested on some pre-defined dataset and it’s performance can be compared to earlier versions. |
| **Prompt Evaluation**   | Dashboard lists experiment runs for a particular dataset. In each experiment run, details of each record run are shown like input, expected output, actual output along with trace info for that run. Results can be filtered by contents like a particular text, score or failures. The navigation through evaluation results is very easy. | Evaluation results are output as .jsonl files. There is no dashboard to view result details. We have to analyse the output file using JSON tools. To filter results by text, error, failure, we have to use custom JSON code. |



**Findings**: 

- Bedrock automatic evaluation offers two modes - model eval and RAG eval, each of which provides pre-built metrics and the capability of customizing metrics. The human-centered evaluation was not explored due to the expectation of having an automatic eval tool for different use cases. 

- The pre-built metrics have their own prompts built-in. The evaluation will be off-chart if the use case does not fit exactly the template provided. 

- Our intent detection use case requires calculating recall, which can be achieved via QA model eval, not the retrieval-only RAG eval. 

- Bedrock evaluation only offers GenAI related metrics using LLM as a judge. Traditional ML metrics for retrieval are not readily available. However, we can reproduce simple metrics (recall@1, recall@3, and recall@5) using prompt. The ability to calculate more advanced metrics (NDCG) using prompt is yet to be explored and the correctness cannot be guaranteed. 

- Given a typical traced dataset without any ground truth, traditional ML metrics for retrieval do not apply. However, we can use LLM as a judge to evaluate the query-document relevancy, and the result highly depends on which LLM/RLM being used. One observation is o4-mini achieved 100% relevancy while sonnet-3.7 achieved 68%, and o4-mini aligns better with human judgement. 

- Customized metrics can be downloaded and is supposed to be reused, should the same metrics apply in the next eval job. However, eval job cannot be created when importing customized metrics. 

- Currently we can list eval jobs via AWS SDK. Creating eval job is still blocked for AWS-Lyrics-PowerUsers. All above-mentioned experiments were executed via AWS console with a new manually created IAM role, which is not assumable from ADP SSO. Once unblocked, SDK and Console should have the same functionality if code is required. 

- The eval results can be examined one by one from the console. 

- Human annotation seems not possible in Bedrock. 

- One advantage of running eval jobs in AWS console is ease of use and dedicated support. One minor disadvantage is it is not as flexible as one would expect in real production use cases. 


https://github.com/strands-agents/samples/tree/main
https://aws.amazon.com/blogs/machine-learning/observing-and-evaluating-ai-agentic-workflows-with-strands-agents-sdk-and-arize-ax/
