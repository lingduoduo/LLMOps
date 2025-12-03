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
    UpdateAppReq,
    GetAppsWithPageReq,
    GetAppsWithPageResp,
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
    """Application controller"""
    app_service: AppService
    retrieval_service: RetrievalService

    @login_required
    def create_app(self):
        """Call service to create a new app record"""
        # 1. Extract request and validate
        req = CreateAppReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Call service to create app info
        app = self.app_service.create_app(req, current_user)

        # 3. Return success response with created app id
        return success_json({"id": app.id})

    @login_required
    def get_app(self, app_id: UUID):
        """Get basic information of a specific app"""
        app = self.app_service.get_app(app_id, current_user)
        resp = GetAppResp()
        return success_json(resp.dump(app))

    @login_required
    def update_app(self, app_id: UUID):
        """Update a specific app based on the provided information"""
        # 1. Extract data and validate
        req = UpdateAppReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Call service to update data
        self.app_service.update_app(app_id, current_user, **req.data)

        return success_message("Successfully updated Agent application")

    @login_required
    def copy_app(self, app_id: UUID):
        """Quickly copy an app based on the given app id"""
        app = self.app_service.copy_app(app_id, current_user)
        return success_json({"id": app.id})

    @login_required
    def delete_app(self, app_id: UUID):
        """Delete a specific app based on the provided information"""
        self.app_service.delete_app(app_id, current_user)
        return success_message("Successfully deleted Agent application")

    @login_required
    def get_apps_with_page(self):
        """Get a paginated list of apps for the current logged-in account"""
        # 1. Extract data and validate
        req = GetAppsWithPageReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Call service to get list data and paginator
        apps, paginator = self.app_service.get_apps_with_page(req, current_user)

        # 3. Build response structure and return
        resp = GetAppsWithPageResp(many=True)

        return success_json(PageModel(list=resp.dump(apps), paginator=paginator))

    @login_required
    def get_draft_app_config(self, app_id: UUID):
        """Get the latest draft configuration for the specified app"""
        draft_config = self.app_service.get_draft_app_config(app_id, current_user)
        return success_json(draft_config)

    @login_required
    def update_draft_app_config(self, app_id: UUID):
        """Update the latest draft configuration for the specified app"""
        # 1. Get draft configuration from request JSON
        draft_app_config = request.get_json(force=True, silent=True) or {}

        # 2. Call service to update the app's draft configuration
        self.app_service.update_draft_app_config(app_id, draft_app_config, current_user)

        return success_message("Successfully updated app draft configuration")

    @login_required
    def publish(self, app_id: UUID):
        """Publish/update a specific draft configuration for the app"""
        self.app_service.publish_draft_app_config(app_id, current_user)
        return success_message("Successfully published/updated app configuration")

    @login_required
    def cancel_publish(self, app_id: UUID):
        """Cancel the published configuration for the specified app"""
        self.app_service.cancel_publish_app_config(app_id, current_user)
        return success_message("Successfully cancelled published app configuration")

    @login_required
    def fallback_history_to_draft(self, app_id: UUID):
        """Rollback a specific historical configuration version to draft for the app"""
        # 1. Extract data and validate
        req = FallbackHistoryToDraftReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Call service to rollback the specified version to draft
        self.app_service.fallback_history_to_draft(app_id, req.app_config_version_id.data, current_user)

        return success_message("Successfully rolled back historical configuration to draft")

    @login_required
    def get_publish_histories_with_page(self, app_id: UUID):
        """Get the publish history list for the specified app"""
        # 1. Get request data and validate
        req = GetPublishHistoriesWithPageReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Call service to get paginated list data
        app_config_versions, paginator = self.app_service.get_publish_histories_with_page(
            app_id, req, current_user
        )

        # 3. Build response structure and return
        resp = GetPublishHistoriesWithPageResp(many=True)

        return success_json(PageModel(list=resp.dump(app_config_versions), paginator=paginator))

    @login_required
    def get_debug_conversation_summary(self, app_id: UUID):
        """Get long-term memory (summary) of the debug conversation for the specified app"""
        summary = self.app_service.get_debug_conversation_summary(app_id, current_user)
        return success_json({"summary": summary})

    @login_required
    def update_debug_conversation_summary(self, app_id: UUID):
        """Update long-term memory (summary) of the debug conversation for the specified app"""
        # 1. Extract data and validate
        req = UpdateDebugConversationSummaryReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Call service to update debug conversation long-term memory
        self.app_service.update_debug_conversation_summary(app_id, req.summary.data, current_user)

        return success_message("Successfully updated AI app long-term memory")

    @login_required
    def delete_debug_conversation(self, app_id: UUID):
        """Clear all debug conversation records for the specified app"""
        self.app_service.delete_debug_conversation(app_id, current_user)
        return success_message("Successfully cleared app debug conversation records")

    @login_required
    def debug_chat(self, app_id: UUID):
        """Start a debug chat with the specified app using the provided query"""
        # 1. Extract data and validate
        req = DebugChatReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Call service to start debug conversation
        response = self.app_service.debug_chat(app_id, req.query.data, current_user)

        return compact_generate_response(response)

    @login_required
    def stop_debug_chat(self, app_id: UUID, task_id: UUID):
        """Stop a specific debug chat task for the given app"""
        self.app_service.stop_debug_chat(app_id, task_id, current_user)
        return success_message("Successfully stopped app debug conversation")

    @login_required
    def get_debug_conversation_messages_with_page(self, app_id: UUID):
        """Get a paginated list of debug conversation messages for the specified app"""
        # 1. Extract request data and validate
        req = GetDebugConversationMessagesWithPageReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Call service to get data
        messages, paginator = self.app_service.get_debug_conversation_messages_with_page(
            app_id, req, current_user
        )

        # 3. Build response structure
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

        ############# Test Functional Call Agents #############
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

        ############# Test Workflow #############
        from internal.core.workflow import Workflow
        from internal.core.workflow.entities.workflow_entity import WorkflowConfig
        from flask_login import current_user

        # 1. Define nodes
        nodes = [
            # ---------- Start node ----------
            {
                "id": "18d938c4-ecd7-4a6b-9403-3625224b96cc",
                "node_type": "start",
                "title": "Start",
                "description": "Workflow entry point; defines user inputs.",
                "inputs": [
                    {
                        "name": "query",
                        "type": "string",
                        "description": "User input query",
                        "required": True,
                        "value": {
                            "type": "generated",
                            "content": "",
                        },
                    },
                    {
                        "name": "location",
                        "type": "string",
                        "description": "User location or city (optional)",
                        "required": False,
                        "value": {
                            "type": "generated",
                            "content": "",
                        },
                    },
                ],
            },

            # ---------- Dataset retrieval node (TEMPORARILY DISABLED) ----------
            # {
            #     "id": "868b5769-1925-4e7b-8aa4-af7c3d444d91",
            #     "node_type": "dataset_retrieval",
            #     "title": "Knowledge Base Retrieval",
            #     "description": "Retrieve relevant documents based on the user query.",
            #     "inputs": [
            #         {
            #             "name": "query",
            #             "type": "string",
            #             "value": {
            #                 "type": "ref",
            #                 "content": {
            #                     "ref_node_id": "18d938c4-ecd7-4a6b-9403-3625224b96cc",
            #                     "ref_var_name": "query",
            #                 },
            #             },
            #         }
            #     ],
            #     "dataset_ids": [
            #         "1cbb6449-5463-49a4-b0ef-1b94cdf747d7",
            #         "798f5324-c82e-44c2-94aa-035afbe88839",
            #     ],
            #     "outputs": [
            #         {
            #             "name": "combine_documents",
            #             "type": "string",
            #             "value": {
            #                 "type": "generated",
            #                 "content": "",
            #             },
            #         },
            #     ],
            # },

            # ---------- HTTP Request Node (Path 1) ----------
            {
                "id": "675fca50-1228-8008-82dc-0c714158534c",
                "node_type": "http_request",
                "title": "HTTP Request",
                "description": "Simple GET request to langchain.com",
                "url": "https://www.langchain.com/",
                "method": "get",
                "inputs": [],
                "outputs": [
                    {
                        "name": "response",
                        "type": "string",
                        "value": {
                            "type": "generated",
                            "content": "",
                        },
                    }
                ],
            },

            # ---------- LLM node (uses HTTP response as context) ----------
            {
                "id": "eba75e0b-21b7-46ed-8d21-791724f0740f",
                "node_type": "llm",
                "title": "Large Language Model",
                "description": "Answer the user query using HTTP response as context.",
                "inputs": [
                    {
                        "name": "query",
                        "type": "string",
                        "value": {
                            "type": "ref",
                            "content": {
                                "ref_node_id": "18d938c4-ecd7-4a6b-9403-3625224b96cc",
                                "ref_var_name": "query",
                            },
                        },
                    },
                    {
                        "name": "context",
                        "type": "string",
                        "value": {
                            "type": "ref",
                            "content": {
                                "ref_node_id": "675fca50-1228-8008-82dc-0c714158534c",  # http_request
                                "ref_var_name": "response",
                            },
                        },
                    },
                ],
                "prompt": (
                    "You are a helpful AI assistant.\n\n"
                    "User question:\n"
                    "{{query}}\n\n"
                    "Relevant context (may be empty):\n"
                    "<context>{{context}}</context>\n\n"
                    "Answer the question as well as you can."
                ),
                "model_config": {
                    "provider": "openai",
                    "model": "gpt-4o-mini",
                    "parameters": {
                        "temperature": 0.3,
                        "top_p": 0.85,
                        "frequency_penalty": 0.2,
                        "presence_penalty": 0.2,
                        "max_tokens": 512,
                    },
                },
            },

            # ---------- Code node (post-process HTTP + LLM) ----------
            {
                "id": "4a9ed43d-e886-49f7-af9f-9e85d83b27aa",
                "node_type": "code",
                "title": "Code Post-processing",
                "description": "Post-process LLM answer and HTTP content with safe defaults.",
                "inputs": [
                    {
                        "name": "combine_documents",
                        "type": "string",
                        "value": {
                            "type": "ref",
                            "content": {
                                "ref_node_id": "675fca50-1228-8008-82dc-0c714158534c",  # http_request
                                "ref_var_name": "response",
                            },
                        },
                    },
                    {
                        "name": "llm_output",
                        "type": "string",
                        "value": {
                            "type": "ref",
                            "content": {
                                "ref_node_id": "eba75e0b-21b7-46ed-8d21-791724f0740f",
                                "ref_var_name": "output",
                            },
                        },
                    },
                ],
                "code": """def main(params):
            # Get HTTP content or default text
            docs = params.get("combine_documents")
            if not docs:
                docs = (
                    "This is default HTTP content for testing. "
                    "It is used when the HTTP request returns empty. "
                    "You can modify this to simulate HTTP outputs."
                )
    
            # Get LLM output or default demo text
            answer = params.get("llm_output")
            if not answer:
                answer = "This is a placeholder LLM answer (for testing)."
    
            snippet = docs[:200]
    
            return {
                "snippet": snippet,
                "answer_length": len(answer),
                "fallback_used": params.get("combine_documents") is None or params.get("combine_documents") == ""
            }""",
                "outputs": [
                    {
                        "name": "snippet",
                        "type": "string",
                        "value": {
                            "type": "generated",
                            "content": "",
                        },
                    },
                    {
                        "name": "answer_length",
                        "type": "int",
                        "value": {
                            "type": "generated",
                            "content": 0,
                        },
                    },
                    {
                        "name": "fallback_used",
                        "type": "boolean",
                        "value": {
                            "type": "generated",
                            "content": False,
                        },
                    },
                ],
            },

            # ---------- Template transform node (Path 1) ----------
            {
                "id": "623b7671-0bc2-446c-bf5e-5e25032a522e",
                "node_type": "template_transform",
                "title": "Template Transform",
                "description": "Combine query, location, LLM answer and snippet into a final message.",
                "inputs": [
                    {
                        "name": "location",
                        "type": "string",
                        "value": {
                            "type": "ref",
                            "content": {
                                "ref_node_id": "18d938c4-ecd7-4a6b-9403-3625224b96cc",
                                "ref_var_name": "location",
                            },
                        },
                    },
                    {
                        "name": "query",
                        "type": "string",
                        "value": {
                            "type": "ref",
                            "content": {
                                "ref_node_id": "18d938c4-ecd7-4a6b-9403-3625224b96cc",
                                "ref_var_name": "query",
                            },
                        },
                    },
                    {
                        "name": "llm_output",
                        "type": "string",
                        "value": {
                            "type": "ref",
                            "content": {
                                "ref_node_id": "eba75e0b-21b7-46ed-8d21-791724f0740f",
                                "ref_var_name": "output",
                            },
                        },
                    },
                    {
                        "name": "snippet",
                        "type": "string",
                        "value": {
                            "type": "ref",
                            "content": {
                                "ref_node_id": "4a9ed43d-e886-49f7-af9f-9e85d83b27aa",
                                "ref_var_name": "snippet",
                            },
                        },
                    },
                ],
                "template": (
                    "Location: {{location}}\n"
                    "User question: {{query}}\n\n"
                    "LLM answer:\n{{llm_output}}\n\n"
                    "HTTP snippet (or default):\n{{snippet}}\n"
                ),
            },

            # ---------- Tool node (google_serper, Path 2) ----------
            {
                "id": "2f6cf40d-0219-421b-92ff-229fdde15ecb",
                "node_type": "tool",
                "title": "Built-in Tool: Google Serper",
                "description": "Call google_serper with the user query.",
                "type": "builtin_tool",
                "provider_id": "google",
                "tool_id": "google_serper",
                "inputs": [
                    {
                        "name": "query",
                        "type": "string",
                        "value": {
                            "type": "ref",
                            "content": {
                                "ref_node_id": "18d938c4-ecd7-4a6b-9403-3625224b96cc",
                                "ref_var_name": "query",
                            },
                        },
                    }
                ],
                "outputs": [
                    {
                        "name": "text",
                        "type": "string",
                        "value": {
                            "type": "generated",
                            "content": "",
                        },
                    }
                ],
            },

            # ---------- End node ----------
            {
                "id": "860c8411-37ed-4872-b53f-30afa0290211",
                "node_type": "end",
                "title": "End",
                "description": "Final output variables of the workflow.",
                "outputs": [
                    {
                        "name": "query",
                        "type": "string",
                        "value": {
                            "type": "ref",
                            "content": {
                                "ref_node_id": "18d938c4-ecd7-4a6b-9403-3625224b96cc",
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
                                "ref_node_id": "18d938c4-ecd7-4a6b-9403-3625224b96cc",
                                "ref_var_name": "location",
                            },
                        },
                    },
                    {
                        "name": "llm_output",
                        "type": "string",
                        "value": {
                            "type": "ref",
                            "content": {
                                "ref_node_id": "eba75e0b-21b7-46ed-8d21-791724f0740f",
                                "ref_var_name": "output",
                            },
                        },
                    },
                    {
                        "name": "template_output",
                        "type": "string",
                        "value": {
                            "type": "ref",
                            "content": {
                                "ref_node_id": "623b7671-0bc2-446c-bf5e-5e25032a522e",
                                "ref_var_name": "output",
                            },
                        },
                    },
                    {
                        "name": "snippet",
                        "type": "string",
                        "value": {
                            "type": "ref",
                            "content": {
                                "ref_node_id": "4a9ed43d-e886-49f7-af9f-9e85d83b27aa",
                                "ref_var_name": "snippet",
                            },
                        },
                    },
                    {
                        "name": "answer_length",
                        "type": "int",
                        "value": {
                            "type": "ref",
                            "content": {
                                "ref_node_id": "4a9ed43d-e886-49f7-af9f-9e85d83b27aa",
                                "ref_var_name": "answer_length",
                            },
                        },
                    },
                    {
                        "name": "fallback_used",
                        "type": "boolean",
                        "value": {
                            "type": "ref",
                            "content": {
                                "ref_node_id": "4a9ed43d-e886-49f7-af9f-9e85d83b27aa",
                                "ref_var_name": "fallback_used",
                            },
                        },
                    },
                    {
                        "name": "google_search_result",
                        "type": "string",
                        "value": {
                            "type": "ref",
                            "content": {
                                "ref_node_id": "2f6cf40d-0219-421b-92ff-229fdde15ecb",
                                "ref_var_name": "text",
                            },
                        },
                    },
                    {
                        "name": "http_response",
                        "type": "string",
                        "value": {
                            "type": "ref",
                            "content": {
                                "ref_node_id": "675fca50-1228-8008-82dc-0c714158534c",
                                "ref_var_name": "response",
                            },
                        },
                    },
                ],
            },
        ]

        # 2. Edges: two active paths (HTTP/LLM chain + tool), retrieval commented out
        edges = [
            # ========= Path 1: HTTP -> LLM -> Code -> Template -> End =========
            {
                "id": "675fca50-1228-4000-8000-000000000001",
                "source": "18d938c4-ecd7-4a6b-9403-3625224b96cc",  # start
                "source_type": "start",
                "target": "675fca50-1228-8008-82dc-0c714158534c",  # http_request
                "target_type": "http_request",
            },
            {
                "id": "675fca50-1228-4000-8000-000000000002",
                "source": "675fca50-1228-8008-82dc-0c714158534c",  # http_request
                "source_type": "http_request",
                "target": "eba75e0b-21b7-46ed-8d21-791724f0740f",  # llm
                "target_type": "llm",
            },
            {
                "id": "675fca50-1228-4000-8000-000000000003",
                "source": "eba75e0b-21b7-46ed-8d21-791724f0740f",  # llm
                "source_type": "llm",
                "target": "4a9ed43d-e886-49f7-af9f-9e85d83b27aa",  # code
                "target_type": "code",
            },
            {
                "id": "675fca50-1228-4000-8000-000000000004",
                "source": "4a9ed43d-e886-49f7-af9f-9e85d83b27aa",  # code
                "source_type": "code",
                "target": "623b7671-0bc2-446c-bf5e-5e25032a522e",  # template_transform
                "target_type": "template_transform",
            },
            {
                "id": "675fca50-1228-4000-8000-000000000005",
                "source": "623b7671-0bc2-446c-bf5e-5e25032a522e",  # template_transform
                "source_type": "template_transform",
                "target": "860c8411-37ed-4872-b53f-30afa0290211",  # end
                "target_type": "end",
            },

            # ========= Path 2: Tool (google_serper) -> End =========
            {
                "id": "675fca50-1228-4000-8000-000000000006",
                "source": "18d938c4-ecd7-4a6b-9403-3625224b96cc",  # start
                "source_type": "start",
                "target": "2f6cf40d-0219-421b-92ff-229fdde15ecb",  # tool
                "target_type": "tool",
            },
            {
                "id": "675fca50-1228-4000-8000-000000000007",
                "source": "2f6cf40d-0219-421b-92ff-229fdde15ecb",  # tool
                "source_type": "tool",
                "target": "860c8411-37ed-4872-b53f-30afa0290211",  # end
                "target_type": "end",
            },
        ]

        # 3. Build workflow & invoke
        workflow = Workflow(
            workflow_config=WorkflowConfig(
                account_id=current_user.id,
                name="workflow_demo_http_and_tool_parallel",
                description=(
                    "Demo workflow with two active parallel paths: "
                    "1) http_request -> llm -> code -> template, "
                    "2) google_serper tool. "
                    "Dataset retrieval is currently commented out."
                ),
                nodes=nodes,
                edges=edges,
            )
        )

        result = workflow.invoke(
            {
                "query": "What prompts are there about front-end?",
                "location": "New Jersey",
            }
        )

        return success_json(
            {
                **result,
                "info": {
                    "name": workflow.name,
                    "description": workflow.description,
                    "args_schema": workflow.args_schema.schema(),
                },
                "node_results": [node_result.dict() for node_result in result["node_results"]],
            }
        )
