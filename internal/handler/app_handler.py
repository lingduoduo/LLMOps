#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : app_handler.py
"""
from dataclasses import dataclass
from uuid import UUID

from flask import request
from flask_login import login_required, current_user
from injector import inject

from internal.schema.app_schema import (
    CreateAppReq,
    GetAppResp,
    GetPublishHistoriesWithPageReq,
    GetPublishHistoriesWithPageResp,
    FallbackHistoryToDraftReq,
    UpdateDebugConversationSummaryReq,
    DebugChatReq,
    GetDebugConversationMessagesWithPageReq,
    GetDebugConversationMessagesWithPageResp
)
from internal.service import AppService, RetrievalService
from pkg.paginator import PageModel
from pkg.response import validate_error_json, success_json, success_message, compact_generate_response


@inject
@dataclass
class AppHandler:
    """Application controller (Flask route handler for app-related operations)"""
    app_service: AppService
    retrieval_service: RetrievalService

    @login_required
    def create_app(self):
        """Create a new application record"""
        # 1. Extract and validate the request data
        req = CreateAppReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Call the service layer to create the app
        app = self.app_service.create_app(req, current_user)

        # 3. Return success response with new app ID
        return success_json({"id": app.id})

    @login_required
    def get_app(self, app_id: UUID):
        """Retrieve basic information of a specific application"""
        app = self.app_service.get_app(app_id, current_user)
        resp = GetAppResp()
        return success_json(resp.dump(app))

    @login_required
    def get_draft_app_config(self, app_id: UUID):
        """Fetch the latest draft configuration of the specified application"""
        draft_config = self.app_service.get_draft_app_config(app_id, current_user)
        return success_json(draft_config)

    @login_required
    def update_draft_app_config(self, app_id: UUID):
        """Update the latest draft configuration of the specified application"""
        # 1. Extract draft configuration from request body
        draft_app_config = request.get_json(force=True, silent=True) or {}

        # 2. Call service to update the draft configuration
        self.app_service.update_draft_app_config(app_id, draft_app_config, current_user)

        return success_message("App draft configuration updated successfully")

    @login_required
    def publish(self, app_id: UUID):
        """Publish or update the current draft configuration of the specified application"""
        self.app_service.publish_draft_app_config(app_id, current_user)
        return success_message("Application configuration published/updated successfully")

    @login_required
    def cancel_publish(self, app_id: UUID):
        """Cancel the published configuration of the specified application"""
        self.app_service.cancel_publish_app_config(app_id, current_user)
        return success_message("Application configuration publication canceled successfully")

    @login_required
    def get_publish_histories_with_page(self, app_id: UUID):
        """Get paginated list of published configuration histories for the application"""
        # 1. Extract and validate request parameters
        req = GetPublishHistoriesWithPageReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Retrieve paginated list data from service
        app_config_versions, paginator = self.app_service.get_publish_histories_with_page(app_id, req, current_user)

        # 3. Build and return paginated response
        resp = GetPublishHistoriesWithPageResp(many=True)
        return success_json(PageModel(list=resp.dump(app_config_versions), paginator=paginator))

    @login_required
    def fallback_history_to_draft(self, app_id: UUID):
        """Revert a historical configuration version back to the draft"""
        # 1. Extract and validate request data
        req = FallbackHistoryToDraftReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Call service to revert the specified version to draft
        self.app_service.fallback_history_to_draft(app_id, req.app_config_version_id.data, current_user)

        return success_message("Historical configuration reverted to draft successfully")

    @login_required
    def get_debug_conversation_summary(self, app_id: UUID):
        """Retrieve long-term memory summary for the application's debug conversation"""
        summary = self.app_service.get_debug_conversation_summary(app_id, current_user)
        return success_json({"summary": summary})

    @login_required
    def update_debug_conversation_summary(self, app_id: UUID):
        """Update the long-term memory summary for the application's debug conversation"""
        # 1. Extract and validate request data
        req = UpdateDebugConversationSummaryReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Call service to update the summary
        self.app_service.update_debug_conversation_summary(app_id, req.summary.data, current_user)

        return success_message("AI application long-term memory updated successfully")

    @login_required
    def delete_debug_conversation(self, app_id: UUID):
        """Clear all debug conversation records for the specified application"""
        self.app_service.delete_debug_conversation(app_id, current_user)
        return success_message("Application debug conversation records cleared successfully")

    @login_required
    def debug_chat(self, app_id: UUID):
        """Initiate a debugging chat session for the specified application"""
        # 1. Extract and validate input data
        req = DebugChatReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Call service to start a debug conversation
        response = self.app_service.debug_chat(app_id, req.query.data, current_user)

        return compact_generate_response(response)

    @login_required
    def stop_debug_chat(self, app_id: UUID, task_id: UUID):
        """Stop a running debug chat session by task ID"""
        self.app_service.stop_debug_chat(app_id, task_id, current_user)
        return success_message("Application debug chat stopped successfully")

    @login_required
    def get_debug_conversation_messages_with_page(self, app_id: UUID):
        """Retrieve paginated debug conversation messages for the application"""
        # 1. Extract and validate query parameters
        req = GetDebugConversationMessagesWithPageReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Retrieve data from the service layer
        messages, paginator = self.app_service.get_debug_conversation_messages_with_page(app_id, req, current_user)

        # 3. Build paginated response
        resp = GetDebugConversationMessagesWithPageResp(many=True)
        return success_json(PageModel(list=resp.dump(messages), paginator=paginator))

    @login_required
    def ping(self):
        # """Health check endpoint"""
        # return {"ping": "pong"}

        # google_serper = self.provider_factory.get_tool("google", "google_serper")()
        # print(google_serper)
        # print(google_serper.invoke("What is the world record for marathon?"))
        # return self.api_tool_service.api_tool_invoke()

        # providers = self.provider_factory.get_builtin_tools()
        # return success_json({
        #     "providers": providers
        # })
        # return self.api_tool_service.api_tool_invoke()

        # demo_task.delay(uuid.uuid4())

        # human_message = "can you explain LLM agent?"
        # ai_message = """An LLM agent is a large-language-model wrapped with memory, tools, and control logic so it can decide what to do next, not just generate text. Instead of answering once, it runs a loop like:
        # observe → think → act (use a tool) → observe → … → answer"""
        # summary = self.conversation_service.summary(human_message, ai_message)
        # return success_json({"summary": summary})

        # human_message = "Hello, I am Ling"
        # ai_message = "I am ChatGPT, what I can do for you?"
        # old_summary = """The human asks the AI to explain an LLM agent. The AI describes an LLM agent as a large language model equipped with memory, tools, and control logic, enabling it to decide on actions beyond just generating text. It operates in a loop of observing, thinking, acting (using a tool), and then observing again."""
        # summary = self.conversation_service.summary(human_message, ai_message)
        # return success_json({"summary": summary})

        # human_message = "Could you please explain what is LLM?"
        # human_message = "Python is a programming language which makes it easy to machine learning"
        # conversation_name = self.conversation_service.generate_suggested_questions(human_message)
        # return success_json({"summary": conversation_name})

        # from internal.core.agent.agents import FunctionCallAgent
        # from internal.core.agent.entities.agent_entity import AgentConfig
        # from langchain_openai import ChatOpenAI
        #
        # agent = FunctionCallAgent(AgentConfig(
        #     llm=ChatOpenAI(model="gpt-4o-mini"),
        #     preset_prompt="You are a poet with 20 years of experience. Please write a poem based on the theme provided by the user.",
        # ))
        # state = agent.run("programmer", [], "")
        # content = state["messages"][-1].content
        #
        # return success_json({"content": content})

        ############# Dataset retrieval tool test #############
        # from internal.entity.dataset_entity import RetrievalStrategy, RetrievalSource
        # dataset_retrieval = self.retrieval_service.create_langchain_tool_from_search(
        #     dateset_ids=["123e4567-e89b-12d3-a456-426614174000"],
        #     account_id=current_user,
        #     tool_name=RetrievalStrategy.SEMANTIC,
        #     k=10,
        #     score=0.5,
        #     retrival_source=RetrievalSource.DEBUGGER,
        # )
        # print(dataset_retrieval.name)
        # print(dataset_retrieval.description)
        # print(dataset_retrieval.args)
        #
        # content = dataset_retrieval.invoke("What is LLM agent?")
        # return success_json({"content": content})

        # from internal.core.agent.agents import FunctionCallAgent
        # from internal.core.agent.entities.agent_entity import AgentConfig
        # from langchain_openai import ChatOpenAI
        # from langchain_core.messages import HumanMessage
        # from internal.core.tools.builtin_tools.providers.google import google_serper
        # import uuid
        #
        # # Initialize the FunctionCallAgent with an OpenAI model and configured tools
        # agent = FunctionCallAgent(
        #     llm=ChatOpenAI(model="gpt-4o-mini"),
        #     agent_config=AgentConfig(
        #         user_id=uuid.uuid4(),  # Generate a random user ID for this request
        #         tools=[google_serper()],  # Register the Google Serper search tool
        #     )
        # )
        #
        # # Invoke the agent with a test query
        # agent_result = agent.invoke({
        #     "messages": [
        #         HumanMessage("Help me search for the top 3 results of the 2024 Beijing Half Marathon.")
        #     ]
        # })
        #
        # # Return the agent result as JSON
        # return success_json({"agent_result": agent_result.model_dump()})

        from internal.core.workflow import Workflow
        from internal.core.workflow.entities.workflow_entity import WorkflowConfig

        # Minimal workflow: Start -> End
        start_id = "11111111-1111-1111-1111-111111111111"
        end_id = "22222222-2222-2222-2222-222222222222"

        nodes = [
            {
                "id": start_id,
                "node_type": "start",
                "title": "Start",
                "description": "Minimal start node for workflow testing.",
                "inputs": [
                    {
                        "name": "query",
                        "type": "string",
                        "description": "User input query",
                        "required": True,
                        "value": {
                            "type": "generated",
                            "content": "",
                        }
                    },
                    {
                        "name": "location",
                        "type": "string",
                        "description": "City/location to query",
                        "required": False,
                        "value": {
                            "type": "generated",
                            "content": "",
                        }
                    },
                ],
            },
            {
                "id": end_id,
                "node_type": "end",
                "title": "End",
                "description": "Minimal end node; just returns inputs and a literal field.",
                "outputs": [
                    {
                        "name": "query",
                        "type": "string",
                        "value": {
                            "type": "ref",
                            "content": {
                                "ref_node_id": start_id,
                                "ref_var_name": "query",
                            },
                        },
                    },
                    {
                        "name": "location",
                        "type": "string",
                        "value": {
                            "type": "ref",
                            "content": {
                                "ref_node_id": start_id,
                                "ref_var_name": "location",
                            },
                        },
                    },
                    {
                        "name": "username",
                        "type": "string",
                        "value": {
                            "type": "literal",
                            "content": "Ling",
                        },
                    },
                ],
            },
        ]

        edges = [
            {
                "id": "33333333-3333-3333-3333-333333333333",
                "source": start_id,
                "source_type": "start",
                "target": end_id,
                "target_type": "end",
            },
        ]

        workflow = Workflow(
            workflow_config=WorkflowConfig(
                account_id=current_user.id,
                name="minimal_workflow",
                description="Minimal workflow: start -> end",
                nodes=nodes,
                edges=edges,
            )
        )

        # Simple test input
        result = workflow.invoke(
            {"query": "Test minimal workflow", "location": "New Jersey"}
        )

        return success_json(
            {
                **result,
                "info": {
                    "name": workflow.name,
                    "description": workflow.description,
                    "args_schema": workflow.args_schema.schema(),
                },
                # If node_results are Pydantic / dataclass-like objects:
                "node_results": [
                    node_result.dict() for node_result in result["node_results"]
                ],
            }
        )
