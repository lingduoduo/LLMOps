#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : assistant_agent_service.py
"""
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Generator
from uuid import UUID

from flask import current_app
from injector import inject
from langchain_core.messages import HumanMessage
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.tools import BaseTool, tool
from sqlalchemy import desc
from sqlalchemy.orm import joinedload

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
    """Assistant agent service"""
    db: SQLAlchemy
    faiss_service: FaissService
    conversation_service: ConversationService

    def chat(self, query, account: Account) -> Generator:
        """Chat with the assistant agent using the given query and account"""
        # 1. Get the assistant agent application ID
        assistant_agent_id = current_app.config.get("ASSISTANT_AGENT_ID")

        # 2. Get or create the assistant agent conversation for the current account
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

        # 4. Use a GPT model as the assistant agent's LLM
        llm = Chat(
            model="gpt-4o-mini",
            temperature=0.8,
            features=[ModelFeature.TOOL_CALL, ModelFeature.AGENT_THOUGHT],
            metadata={},
        )

        # 5. Initialize token-buffer memory for short-term conversation history
        token_buffer_memory = TokenBufferMemory(
            db=self.db,
            conversation=conversation,
            model_instance=llm,
        )
        history = token_buffer_memory.get_history_prompt_messages(message_limit=3)

        # 6. Convert draft configuration tools into LangChain tools
        tools = [
            self.faiss_service.convert_faiss_to_tool(),
            self.convert_create_app_to_tool(account.id),
        ]

        # 7. Build the agent using FunctionCallAgent
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
            # 8. Extract thought and answer
            event_id = str(agent_thought.id)

            # 9. Aggregate agent thoughts for database persistence
            if agent_thought.event != QueueEvent.PING:
                # 10. AGENT_MESSAGE events are accumulated; others overwrite
                if agent_thought.event == QueueEvent.AGENT_MESSAGE:
                    if event_id not in agent_thoughts:
                        # 11. Initialize agent message event
                        agent_thoughts[event_id] = agent_thought
                    else:
                        # 12. Append streaming agent message
                        agent_thoughts[event_id] = agent_thoughts[event_id].model_copy(update={
                            "thought": agent_thoughts[event_id].thought + agent_thought.thought,
                            "message": agent_thought.message,
                            "message_token_count": agent_thought.message_token_count,
                            "message_unit_price": agent_thought.message_unit_price,
                            "message_price_unit": agent_thought.message_price_unit,
                            "answer": agent_thoughts[event_id].answer + agent_thought.answer,
                            "answer_token_count": agent_thought.answer_token_count,
                            "answer_unit_price": agent_thought.answer_unit_price,
                            "answer_price_unit": agent_thought.answer_price_unit,
                            "total_token_count": agent_thought.total_token_count,
                            "total_price": agent_thought.total_price,
                            "latency": agent_thought.latency,
                        })
                else:
                    # 13. Handle other event types
                    agent_thoughts[event_id] = agent_thought

            # 14. Stream SSE-compatible response
            data = {
                **agent_thought.model_dump(include={
                    "event",
                    "thought",
                    "observation",
                    "tool",
                    "tool_input",
                    "answer",
                    "latency",
                    "total_token_count",
                }),
                "id": event_id,
                "conversation_id": str(conversation.id),
                "message_id": str(message.id),
                "task_id": str(agent_thought.task_id),
            }
            yield f"event: {agent_thought.event}\ndata:{json.dumps(data)}\n\n"

        # 15. Persist messages and agent reasoning traces to the database
        self.conversation_service.save_agent_thoughts(
            account_id=account.id,
            app_id=assistant_agent_id,
            app_config={"long_term_memory": {"enable": True}},
            conversation_id=conversation.id,
            message_id=message.id,
            agent_thoughts=list(agent_thoughts.values()),
        )

    @classmethod
    def stop_chat(cls, task_id: UUID, account: Account) -> None:
        """Stop an in-progress assistant agent response"""
        AgentQueueManager.set_stop_flag(task_id, InvokeFrom.ASSISTANT_AGENT, account.id)

    def get_conversation_messages_with_page(
            self, req: GetAssistantAgentMessagesWithPageReq, account: Account
    ) -> tuple[list[Message], Paginator]:
        """Retrieve paginated assistant agent messages for the current account"""
        # 1. Get the assistant agent conversation
        conversation = account.assistant_agent_conversation

        # 2. Build paginator and cursor filters
        paginator = Paginator(db=self.db, req=req)
        filters = []
        if req.created_at.data:
            created_at_datetime = datetime.fromtimestamp(req.created_at.data)
            filters.append(Message.created_at <= created_at_datetime)

        # 3. Execute paginated query
        messages = paginator.paginate(
            self.db.session.query(Message)
            .options(joinedload(Message.agent_thoughts))
            .filter(
                Message.conversation_id == conversation.id,
                Message.status.in_([MessageStatus.STOP, MessageStatus.NORMAL]),
                Message.answer != "",
                *filters,
            )
            .order_by(desc("created_at"))
        )

        return messages, paginator

    def delete_conversation(self, account: Account) -> None:
        """Clear the assistant agent conversation for the given account"""
        self.update(account, assistant_agent_conversation_id=None)

    @classmethod
    def convert_create_app_to_tool(cls, account_id: UUID) -> BaseTool:
        """Define a LangChain tool for auto-creating an Agent / App"""

        class CreateAppInput(BaseModel):
            """Input schema for creating an Agent / App"""
            name: str = Field(description="Name of the Agent/App (max 50 characters)")
            description: str = Field(description="Detailed description of the Agent/App")

        @tool("create_app", args_schema=CreateAppInput)
        def create_app(name: str, description: str) -> str:
            """
            If the user requests creation of an Agent/App, invoke this tool.
            Inputs are the app name and description; output is a success message.
            """
            # 1. Trigger asynchronous backend task
            auto_create_app.delay(name, description, account_id)

            # 2. Return success message
            return (
                "Backend async task triggered to create an Agent app.\n"
                f"App name: {name}\n"
                f"App description: {description}"
            )

        return create_app
