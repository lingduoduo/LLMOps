#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : analysis_service.py
"""
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from injector import inject
from redis import Redis

from internal.model import Account, App, Message
from pkg.sqlalchemy import SQLAlchemy
from .app_service import AppService
from .base_service import BaseService


@inject
@dataclass
class AnalysisService(BaseService):
    """Service for statistical analysis."""
    db: SQLAlchemy
    redis_client: Redis
    app_service: AppService

    def get_app_analysis(self, app_id: UUID, account: Account) -> dict[str, Any]:
        """Return analytical data for a specific app based on its ID and the owning account."""
        # 1. Retrieve and validate the requested app
        app = self.app_service.get_app(app_id, account)

        # 2. Compute today’s time boundaries and past windows
        today = datetime.now()
        today_midnight = datetime.combine(today, datetime.min.time())
        seven_days_ago = today_midnight - timedelta(days=7)
        fourteen_days_ago = today_midnight - timedelta(days=14)

        # 3. Construct Redis cache key
        cache_key = f"{today.strftime('%Y_%m_%d')}:{str(app.id)}"

        # 4. Try loading cached analysis data
        try:
            if self.redis_client.exists(cache_key):
                cached = self.redis_client.get(cache_key)
                return json.loads(cached)
        except Exception:
            pass  # Ignore cache failure and recompute

        # 5. Load messages from the past 7 days and the previous 7-day window before that
        seven_days_messages = self.get_messages_by_time_range(app, seven_days_ago, today_midnight)
        fourteen_days_messages = self.get_messages_by_time_range(app, fourteen_days_ago, seven_days_ago)

        # 6. Compute key metrics: total messages, active users, avg interactions, token speed, cost
        seven_overview = self.calculate_overview_indicators_by_messages(seven_days_messages)
        fourteen_overview = self.calculate_overview_indicators_by_messages(fourteen_days_messages)

        # 7. Compute period-over-period growth
        pop = self.calculate_pop_by_overview_indicators(seven_overview, fourteen_overview)

        # 8. Calculate trend curves over the 7-day window
        trend = self.calculate_trend_by_messages(today_midnight, 7, seven_days_messages)

        # 9. Define metric fields
        fields = [
            "total_messages", "active_accounts", "avg_of_conversation_messages",
            "token_output_rate", "cost_consumption",
        ]

        # 10. Build the final analysis response
        app_analysis = {
            **trend,
            **{
                field: {
                    "data": seven_overview.get(field),
                    "pop": pop.get(field),
                } for field in fields
            }
        }

        # 11. Cache the computed result for 1 day
        self.redis_client.setex(cache_key, 24 * 60 * 60, json.dumps(app_analysis))

        return app_analysis

    def get_messages_by_time_range(self, app: App, start_at: datetime, end_at: datetime) -> list[Message]:
        """Return all messages for the given app within the specified time range."""
        return self.db.session.query(Message).with_entities(
            Message.id, Message.conversation_id, Message.created_by,
            Message.latency, Message.total_token_count, Message.total_price,
            Message.created_at,
        ).filter(
            Message.app_id == app.id,
            Message.created_at >= start_at,
            Message.created_at < end_at,
            Message.answer != "",
        ).all()

    @classmethod
    def calculate_overview_indicators_by_messages(cls, messages: list[Message]) -> dict[str, Any]:
        """
        Compute high-level metrics based on the provided messages:
        - total messages
        - active users
        - average interactions per conversation
        - token output rate
        - total cost
        """
        total_messages = len(messages)
        active_accounts = len({msg.created_by for msg in messages})

        # Average interactions per conversation
        avg_of_conversation_messages = 0
        conversation_count = len({msg.conversation_id for msg in messages})
        if conversation_count != 0:
            avg_of_conversation_messages = total_messages / conversation_count

        # Token output rate (tokens per second)
        token_output_rate = 0
        latency_sum = sum(msg.latency for msg in messages)
        if latency_sum != 0:
            token_output_rate = sum(msg.total_token_count for msg in messages) / latency_sum

        # Total cost
        cost_consumption = sum(msg.total_price for msg in messages)

        return {
            "total_messages": total_messages,
            "active_accounts": active_accounts,
            "avg_of_conversation_messages": float(avg_of_conversation_messages),
            "token_output_rate": float(token_output_rate),
            "cost_consumption": float(cost_consumption),
        }

    @classmethod
    def calculate_pop_by_overview_indicators(
            cls, current_data: dict[str, Any], previous_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Calculate period-over-period (PoP) growth for each metric."""
        pop = {}
        fields = [
            "total_messages", "active_accounts", "avg_of_conversation_messages",
            "token_output_rate", "cost_consumption",
        ]

        for field in fields:
            current_value = current_data.get(field)
            previous_value = previous_data.get(field)

            if previous_value != 0:
                pop[field] = (current_value - previous_value) / previous_value
            else:
                pop[field] = 0

        return pop

    @classmethod
    def calculate_trend_by_messages(
            cls, end_at: datetime, days_ago: int, messages: list[Message]
    ) -> dict[str, Any]:
        """Compute daily trend curves over a specified number of days."""
        end_at = datetime.combine(end_at, datetime.min.time())

        total_messages_trend = {"x_axis": [], "y_axis": []}
        active_accounts_trend = {"x_axis": [], "y_axis": []}
        avg_of_conversation_messages_trend = {"x_axis": [], "y_axis": []}
        cost_consumption_trend = {"x_axis": [], "y_axis": []}

        for day in range(days_ago):
            trend_start_at = end_at - timedelta(days_ago - day)
            trend_end_at = end_at - timedelta(days_ago - day - 1)

            # Total messages
            daily_messages = [
                msg for msg in messages
                if trend_start_at <= msg.created_at < trend_end_at
            ]
            total_messages_value = len(daily_messages)
            total_messages_trend["x_axis"].append(int(trend_start_at.timestamp()))
            total_messages_trend["y_axis"].append(total_messages_value)

            # Active accounts
            active_accounts_value = len({msg.created_by for msg in daily_messages})
            active_accounts_trend["x_axis"].append(int(trend_start_at.timestamp()))
            active_accounts_trend["y_axis"].append(active_accounts_value)

            # Average interactions per conversation
            conversation_ids = {msg.conversation_id for msg in daily_messages}
            if len(conversation_ids) != 0:
                avg_value = total_messages_value / len(conversation_ids)
            else:
                avg_value = 0
            avg_of_conversation_messages_trend["x_axis"].append(int(trend_start_at.timestamp()))
            avg_of_conversation_messages_trend["y_axis"].append(avg_value)

            # Cost trend
            cost_value = sum(msg.total_price for msg in daily_messages)
            cost_consumption_trend["x_axis"].append(int(trend_start_at.timestamp()))
            cost_consumption_trend["y_axis"].append(cost_value)

        return {
            "total_messages_trend": total_messages_trend,
            "active_accounts_trend": active_accounts_trend,
            "avg_of_conversation_messages_trend": avg_of_conversation_messages_trend,
            "cost_consumption_trend": cost_consumption_trend,
        }
