# LLMOps

#### **1. Frontend Layer**

- **Tech Stack:** React + WebSocket
- **Functions:**
    - Implements the WebUI (web interface)
    - Provides identity authentication
    - Ensures cross-platform compatibility

------

#### **2. Chat Engine**

- **Tech Stack:** LangChain + Flask + Redis
- **Functions:**
    - Orchestrates multi-Agent dialogue flows
    - Handles coordination and turn-taking
    - Maintains conversational context (session persistence)

------

#### **3. Intent Recognition**

- **Tech Stack:** Sklearn + BERT + ONNX
- **Functions:**
    - Integrates multiple model types for intent classification
    - Supports model fusion and hot updates

------

#### **4. Knowledge Base Retrieval**

- **Tech Stack:** Elasticsearch + Weaviate + Neo4j
- **Functions:**
    - Enables multi-source retrieval and hybrid search
    - Performs graph reasoning and relationship inference

------

#### **5. Backend Services**

- **Tech Stack:** Flask + PostgreSQL + Redis
- **Functions:**
    - Manages user authentication and access control
    - Maintains audit and operation logs

------

#### **6. Deployment Platform**

- **Tech Stack:** Docker + Kubernetes
- **Functions:**
    - Supports multi-environment deployment
    - Provides elasticity and automatic scaling

------

#### **7. Monitoring and Observability**

- **Tech Stack:** Prometheus + Grafana + Arize
- **Functions:**
    - Implements full-chain monitoring and alerting
    - Enables system-level log aggregation and analysis

### App Framework for Backend Services

```
.
├── app
│         ├── __init__.py
│         └── http
│             ├── __init__.py
│             ├── app.py
│             ├── module.py
│             └── storage
│                 └── log
│                     ├── app.log
│                     ├── app.log.2025-09-14
│                     └── app.log.2025-10-31
├── arize.pem
├── config
│         ├── __init__.py
│         ├── config.py
│         └── default_config.py
├── internal
│         ├── __init__.py
│         ├── __pycache__
│         │         └── __init__.cpython-310.pyc
│         ├── core
│         │         ├── __init__.py
│         │         ├── agent
│         │         │         ├── __init__.py
│         │         │         ├── agents
│         │         │         │         ├── __init__.py
│         │         │         │         ├── agent_queue_manager.py
│         │         │         │         ├── base_agent.py
│         │         │         │         └── function_call_agent.py
│         │         │         └── entities
│         │         │             ├── __init__.py
│         │         │             ├── __pycache__
│         │         │             ├── agent_entity.py
│         │         │             └── queue_entity.py
│         │         ├── file_extractor
│         │         │         ├── __init__.py
│         │         │         └── file_extractor.py
│         │         ├── memory
│         │         │         ├── __init__.py
│         │         │         └── token_buffer_memory.py
│         │         ├── retrievers
│         │         │         ├── __init__.py
│         │         │         ├── full_text_retriever.py
│         │         │         └── semantic_retriever.py
│         │         └── tools
│         │             ├── __init__.py
│         │             ├── api_tools
│         │             │         ├── __init__.py
│         │             │         ├── entities
│         │             │         └── providers
│         │             └── builtin_tools
│         │                 ├── __init__.py
│         │                 ├── categories
│         │                 ├── entities
│         │                 └── providers
│         ├── entity
│         │         ├── __init__.py
│         │         ├── cache_entity.py
│         │         ├── conversation_entity.py
│         │         ├── dataset_entity.py
│         │         ├── jieba_entity.py
│         │         └── upload_file_entity.py
│         ├── exception
│         │         ├── __init__.py
│         │         └── exception.py
│         ├── extension
│         │         ├── __init__.py
│         │         ├── celery_extension.py
│         │         ├── database_extension.py
│         │         ├── logging_extension.py
│         │         ├── login_extension.py
│         │         ├── migrate_extension.py
│         │         └── redis_extension.py
│         ├── handler
│         │         ├── __init__.py
│         │         ├── api_tool_handler.py
│         │         ├── app_handle_bk.py
│         │         ├── app_handler.py
│         │         ├── builtin_tool_handler.py
│         │         ├── dataset_handler.py
│         │         ├── document_handler.py
│         │         ├── segment_handler.py
│         │         └── upload_file_handler.py
│         ├── lib
│         │         ├── __init__.py
│         │         └── helper.py
│         ├── middleware
│         │         ├── __init__.py
│         │         └── middleware.py
│         ├── migration
│         │         ├── alembic.ini
│         │         ├── env.py
│         │         ├── README
│         │         ├── script.py.mako
│         │         └── versions
│         │             ├── 3929b8c595b2_.py
│         │             ├── d574c06f229f_.py
│         │             ├── e9355133b2f5_.py
│         │             └── fcf18e2f1c1d_.py
│         ├── model
│         │         ├── __init__.py
│         │         ├── __pycache__
│         │         │         ├── __init__.cpython-310.pyc
│         │         │         ├── account.cpython-310.pyc
│         │         │         ├── api_tool.cpython-310.pyc
│         │         │         ├── app.cpython-310.pyc
│         │         │         ├── conversation.cpython-310.pyc
│         │         │         ├── dataset.cpython-310.pyc
│         │         │         └── upload_file.cpython-310.pyc
│         │         ├── account.py
│         │         ├── api_tool.py
│         │         ├── app.py
│         │         ├── conversation.py
│         │         ├── dataset.py
│         │         └── upload_file.py
│         ├── router
│         │         ├── __init__.py
│         │         └── router.py
│         ├── schedule
│         │         └── __init__.py
│         ├── schema
│         │         ├── __init__.py
│         │         ├── api_tool_schema.py
│         │         ├── app_schema.py
│         │         ├── dataset_schema.py
│         │         ├── document_schema.py
│         │         ├── schema.py
│         │         ├── segment_schema.py
│         │         └── upload_file_schema.py
│         ├── server
│         │         ├── __init__.py
│         │         └── http.py
│         ├── service
│         │         ├── __init__.py
│         │         ├── account_service.py
│         │         ├── api_tool_service.py
│         │         ├── app_service.py
│         │         ├── aws_service.py
│         │         ├── base_service.py
│         │         ├── builtin_tool_service.py
│         │         ├── conversation_service.py
│         │         ├── dataset_service.py
│         │         ├── document_service.py
│         │         ├── embeddings_service.py
│         │         ├── indexing_service.py
│         │         ├── jieba_service.py
│         │         ├── jwt_service.py
│         │         ├── keyword_table_service.py
│         │         ├── process_rule_service.py
│         │         ├── retrieval_service.py
│         │         ├── segment_service.py
│         │         ├── upload_file_service.py
│         │         └── vector_database_service.py
│         └── task
│             ├── __init__.py
│             ├── dataset_task.py
│             ├── demo_task.py
│             └── document_task.py
├── notes.md
├── pkg
│         ├── __init__.py
│         ├── __pycache__
│         │         └── __init__.cpython-310.pyc
│         ├── paginator
│         │         ├── __init__.py
│         │         └── paginator.py
│         ├── password
│         │         ├── __init__.py
│         │         └── password.py
│         ├── response
│         │         ├── __init__.py
│         │         ├── http_code.py
│         │         └── response.py
│         └── sqlalchemy
│             ├── __init__.py
│             └── sqlalchemy.py
├── pytest.ini
├── RAG.png
├── RAG2.png
├── README.md
├── requirements.txt
├── storage
│         ├── log
│         │         ├── app.log
│         │         ├── app.log.2025-09-20
│         │         └── celery.log
│         └── memory
│             └── chat_history.txt
├── test
│         ├── __init__.py
│         ├── conftest.py
│         ├── internal
│         │         └── handler
│         │             ├── __init__.py
│         │             ├── storage
│         │             │         └── log
│         │             ├── test_api_tool_handler.py
│         │             ├── test_app_handler.py
│         │             └── test_builtin_tool_handler.py
│         └── pkg
│             ├── __init__.py
│             ├── __pycache__
│             │         └── __init__.cpython-310.pyc
│             ├── password
│             │         ├── __init__.py
│             │         ├── storage
│             │         │         └── log
│             │         └── test_password.py
│             └── storage
│                 └── log
│                     └── app.log
├── test.py
└── tmp
```

### Start PostgreSQL server

```
brew services restart postgresql@16
brew services stop postgresql@16
```

### Flask-Migrate

```
pip install flask-migrate

flask db init

flask --app app.http.app routes

flask --app app.http.app db init

flask --app app.http.app db migrate -m "init db migration"

flask --app app.http.app db current -v   # shows DB’s current revision (likely None right now)
flask --app app.http.app db heads        # shows code head (you saw e9355133b2f5)
```

### Redis

```
docker pull redis
docker images
docker run --name redis-dev -d -p 6379:6379 redis
docker exec -it redis-dev redis-cli -p 6379 PING 

docker ps
docker start redis-dev
docker stop redis-dev

docker exec -it redis-dev redis-cli
```

### Weaviate

```
docker images
docker run --name weaviate-dev -d -p 8080:8080 -p 50051:50051 cr.weaviate.io/semitechnologies/weaviate:1.32.8
docker ps
docker stop weaviate-dev
docker start weaviate-dev
```

### Phoenix

```
export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:6006/v1/traces"  # or wherever Phoenix is hosted
export OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
export OTEL_TRACES_EXPORTER=otlp
export OTEL_SERVICE_NAME=openai-test
```

### BedRock

In AWS CloudShell

```
python3 -m venv ~/.venv
source ~/.venv/bin/activate
pip install ipython

aws bedrock list-foundation-models
```

```
import boto3
bedrock_client = boto3.client(service_name="bedrock")
bedrock_client.list_foundation_models()
```

```
ssh-keygen -t rsa
cat .ssh/id_rsa.pub
git clone git@github.com:aws-samples/amazon-bedrock-workshop.git
```

### Celery

```
celery -A app.http.app.celery worker --loglevel INFO --logfile storage/log/celery.log
```

### Arize

```
openssl s_client -connect otlp.arize.com:443 -showcerts </dev/null  | awk '/BEGIN CERTIFICATE/{f="y"} f{print} /END CERTIFICATE/{f=""}' \

chmod 755  /Users/linghuang/Git/LLMOps/study-template/arize-ax/otlp.arize.com.chain.pem

openssl s_client -servername otlp.arize.com -connect otlp.arize.com:443 -showcerts </dev/null 2>/dev/null \
| awk '/BEGIN CERTIFICATE/,/END CERTIFICATE/' \
> "/Users/linghuang/Git/LLMOps/study-template/arize-ax/otlp.arize.com.chain.pem"


import certifi
os.environ['GRPC_DEFAULT_SSL_ROOTS_FILE_PATH'] = "LLMOps/study-template/arize-ax/otlp.arize.com.chain.pem"

import certifi
os.environ['GRPC_DEFAULT_SSL_ROOTS_FILE_PATH'] = certifi.where()

```

## Pytest

```
pytest -q test/internal/handler/test_app_handler.py::TestAppHandler::test_completion -q -s
```

### JWT

Generate JWT_SECRET_KEY

```
openssl rand -base64 24 | tr -dc 'A-Za-z0-9' | head -c 32; echo
```

### OLLMA

http://127.0.0.1:11434/api/generate

```
ollama
ollama list
ollama run deepseek-r1:1.5b

writing manifest
success
>>> hello
Hello! How can I assist you today? 😊

>>> /?
Available Commands:
  /set            Set session variables
  /show           Show model information
  /load <model>   Load a session or model
  /save <model>   Save your current session
  /clear          Clear session context
  /bye            Exit
  /?, /help       Help for a command
  /? shortcuts    Help for keyboard shortcuts

Use """ to begin a multi-line message.

>>> /bye
ollama stop deepseek-r1:1.5b
```

### Disclaimer

This repository and its contents are collected and shared solely for academic and research purposes.
All code, data, and related materials are intended to support independent study, experimentation, and learning.

If you believe any part of this repository inadvertently includes content that should not be shared publicly or may
cause concern, please contact me immediately. I will review and, if necessary, remove the material without delay.

I do not claim ownership of any third-party data or content and have made every effort to respect intellectual property
and privacy rights.
