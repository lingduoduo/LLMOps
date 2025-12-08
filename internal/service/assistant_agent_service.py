#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : assistant_agent_service.py
"""
import json
from dataclasses import dataclass
from datetime import datetime
from threading import Thread
from typing import Generator
from uuid import UUID

from flask import current_app
from injector import inject
from langchain_core.messages import HumanMessage
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.tools import BaseTool, tool
from sqlalchemy import desc

from internal.core.agent.agents import AgentQueueManager, FunctionCallAgent
from internal.core.agent.entities.agent_entity import AgentConfig
from internal.core.agent.entities.queue_entity import QueueEvent
from internal.core.language_model.entities.model_entity import ModelFeature
from internal.core.language_model.providers.openai.chat import Chat
from internal.core.memory import TokenBufferMemory
from internal.entity.conversation_entity import InvokeFrom, MessageStatus
from internal.model import Account, Message
from internal.schema.assistant_agent_schema import GetAssistantAgentMessagesWithPageReq
from internal.task.app_task import auto_create_app
from pkg.paginator import Paginator
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService
from .conversation_service import ConversationService
from .faiss_service import FaissService


@inject
@dataclass
class AssistantAgentService(BaseService):
    """Assistant Agent service"""
    db: SQLAlchemy
    faiss_service: FaissService
    conversation_service: ConversationService

    def chat(self, query, account: Account) -> Generator:
        """Send query + account information to have a conversation with the Assistant Agent"""
        # 1. Retrieve Assistant Agent's app ID
        assistant_agent_id = current_app.config.get("ASSISTANT_AGENT_ID")

        # 2. Retrieve the user's debugging conversation session
        conversation = account.assistant_agent_conversation

        # 3. Create a new message record
        message = self.create(
            Message,
            app_id=assistant_agent_id,
            conversation_id=conversation.id,
            invoke_from=InvokeFrom.DEBUGGER,
            created_by=account.id,
            query=query,
            status=MessageStatus.NORMAL,
        )

        # 4. Use GPT model as the Assistant Agent's LLM
        llm = Chat(
            model="gpt-4o-mini",
            temperature=0.8,
            features=[ModelFeature.TOOL_CALL, ModelFeature.AGENT_THOUGHT],
            metadata={},
        )
        # llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.8)

        # 5. TokenBufferMemory extracts short-term memory
        token_buffer_memory = TokenBufferMemory(
            db=self.db,
            conversation=conversation,
            model_instance=llm,
        )
        history = token_buffer_memory.get_history_prompt_messages(message_limit=3)

        # 6. Convert tools defined in draft config to LangChain tools
        tools = [
            self.faiss_service.convert_faiss_to_tool(),
            self.convert_create_app_to_tool(account.id),
        ]

        print("TOOLS:", tools, "TYPES:", [type(t) for t in tools])

        # 7. Build the Agent using FunctionCallAgent
        agent = FunctionCallAgent(
            llm=llm,
            agent_config=AgentConfig(
                user_id=account.id,
                invoke_from=InvokeFrom.ASSISTANT_AGENT,
                enable_long_term_memory=True,
                tools=tools,
            ),
        )

        agent_thoughts = {}
        for agent_thought in agent.stream({
            "messages": [HumanMessage(query)],
            "history": history,
            "long_term_memory": conversation.summary,
        }):
            # 8. Extract thought + answer
            event_id = str(agent_thought.id)

            # 9. Fill data into agent_thought for storing in database
            if agent_thought.event != QueueEvent.PING:
                # 10. Only AGENT_MESSAGE is accumulated; others overwrite
                if agent_thought.event == QueueEvent.AGENT_MESSAGE:
                    if event_id not in agent_thoughts:
                        # 11. Initialize agent message event
                        agent_thoughts[event_id] = agent_thought
                    else:
                        # 12. Accumulate thought + answer
                        agent_thoughts[event_id] = agent_thoughts[event_id].model_copy(update={
                            "thought": agent_thoughts[event_id].thought + agent_thought.thought,
                            "answer": agent_thoughts[event_id].answer + agent_thought.answer,
                            "latency": agent_thought.latency,
                        })
                else:
                    # 13. Process other event types (overwrite)
                    agent_thoughts[event_id] = agent_thought
            data = {
                **agent_thought.model_dump(include={
                    "event", "thought", "observation", "tool", "tool_input", "answer", "latency",
                }),
                "id": event_id,
                "conversation_id": str(conversation.id),
                "message_id": str(message.id),
                "task_id": str(agent_thought.task_id),
            }
            yield f"event: {agent_thought.event}\ndata:{json.dumps(data)}\n\n"

        # 22. Save message + reasoning process into database asynchronously
        thread = Thread(
            target=self.conversation_service.save_agent_thoughts,
            kwargs={
                "flask_app": current_app._get_current_object(),
                "account_id": account.id,
                "app_id": assistant_agent_id,
                "app_config": {
                    "long_term_memory": {"enable": True},
                },
                "conversation_id": conversation.id,
                "message_id": message.id,
                "agent_thoughts": [agent_thought for agent_thought in agent_thoughts.values()],
            }
        )
        thread.start()

    @classmethod
    def stop_chat(cls, task_id: UUID, account: Account) -> None:
        """Stop a particular chat session using task_id + account"""
        AgentQueueManager.set_stop_flag(task_id, InvokeFrom.ASSISTANT_AGENT, account.id)

    def get_conversation_messages_with_page(
            self, req: GetAssistantAgentMessagesWithPageReq, account: Account
    ) -> tuple[list[Message], Paginator]:
        """Retrieve paginated message list for Assistant Agent conversation based on request + account"""
        # 1. Retrieve conversation
        conversation = account.assistant_agent_conversation

        # 2. Build paginator and cursor filters
        paginator = Paginator(db=self.db, req=req)
        filters = []
        if req.created_at.data:
            # 3. Convert timestamp to datetime
            created_at_datetime = datetime.fromtimestamp(req.created_at.data)
            filters.append(Message.created_at <= created_at_datetime)

        # 4. Execute pagination + filtering
        messages = paginator.paginate(
            self.db.session.query(Message).filter(
                Message.conversation_id == conversation.id,
                Message.status.in_([MessageStatus.STOP, MessageStatus.NORMAL]),
                Message.answer != "",
                *filters,
            ).order_by(desc("created_at"))
        )

        return messages, paginator

    def delete_conversation(self, account: Account) -> None:
        """Clear all Assistant Agent conversation messages for the given account"""
        self.update(account, assistant_agent_conversation_id=None)

    @classmethod
    def convert_create_app_to_tool(cls, account_id: UUID) -> BaseTool:
        """Define LangChain tool for auto-creating an Agent application"""

        class CreateAppInput(BaseModel):
            """Input schema for creating an Agent/Application"""
            name: str = Field(description="Name of the Agent/Application (maximum 50 characters)")
            description: str = Field(
                description="Description of the Agent/Application; clearly summarize its functionality")

        @tool("create_app", args_schema=CreateAppInput)
        def create_app(name: str, description: str) -> str:
            """When the user requests to create an Agent/Application, you may call this tool.
            The input parameters are: application name + description.
            The returned result is a success message after creation.
            """
            # 1. Trigger a Celery asynchronous task to create the application in the backend
            auto_create_app.delay(name, description, account_id)

            # 2. Return a success message
            return (
                f"Successfully invoked the backend async task to create the Agent application.\n"
                f"Application Name: {name}\n"
                f"Application Description: {description}"
            )

        return create_app
