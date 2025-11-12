#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : agent_queue_manager.py
"""
import queue
import time
import uuid
from queue import Queue
from typing import Generator
from uuid import UUID

from redis import Redis

from internal.core.agent.entities.queue_entity import AgentQueueEvent, QueueEvent
from internal.entity.conversation_entity import InvokeFrom


class AgentQueueManager:
    """Agent queue manager that handles event publishing, listening, and task lifecycle control."""

    q: Queue
    user_id: UUID
    task_id: UUID
    invoke_from: InvokeFrom
    redis_client: Redis

    def __init__(
            self,
            user_id: UUID,
            task_id: UUID,
            invoke_from: InvokeFrom,
            redis_client: Redis,
    ) -> None:
        """Initialize the agent queue manager."""
        # 1. Initialize core attributes
        self.q = Queue()
        self.user_id = user_id
        self.task_id = task_id
        self.invoke_from = invoke_from
        self.redis_client = redis_client

        # 2. Determine cache key prefix based on the type of user (debugger/app/service API)
        user_prefix = "account" if invoke_from in [InvokeFrom.WEB_APP, InvokeFrom.DEBUGGER] else "end-user"

        # 3. Set task-specific cache key to indicate that this task has started
        self.redis_client.setex(
            self.generate_task_belong_cache_key(task_id),
            1800,  # cache expires in 30 minutes
            f"{user_prefix}-{str(user_id)}",
        )

    def listen(self) -> Generator:
        """Listen to the queue and yield streaming data events."""
        # 1. Define timeout parameters and initialize timers
        listen_timeout = 600  # maximum listening time (10 minutes)
        start_time = time.time()
        last_ping_time = 0

        # 2. Continuously read data from the queue until timeout or stop signal
        while True:
            try:
                # 3. Fetch data from the queue and yield if available
                item = self.q.get(timeout=1)
                if item is None:
                    break
                yield item
            except queue.Empty:
                continue
            finally:
                # 4. Calculate total elapsed time
                elapsed_time = time.time() - start_time

                # 5. Send a ping event every 10 seconds
                if elapsed_time // 10 > last_ping_time:
                    self.publish(
                        AgentQueueEvent(
                            id=uuid.uuid4(),
                            task_id=self.task_id,
                            event=QueueEvent.PING,
                        )
                    )
                    last_ping_time = elapsed_time // 10

                # 6. Trigger a timeout event if the total listening time exceeds limit
                if elapsed_time >= listen_timeout:
                    self.publish(
                        AgentQueueEvent(
                            id=uuid.uuid4(),
                            task_id=self.task_id,
                            event=QueueEvent.TIMEOUT,
                        )
                    )

                # 7. If the task has been stopped, emit a STOP event
                if self._is_stopped():
                    self.publish(
                        AgentQueueEvent(
                            id=uuid.uuid4(),
                            task_id=self.task_id,
                            event=QueueEvent.STOP,
                        )
                    )

    def stop_listen(self) -> None:
        """Stop listening to the queue."""
        self.q.put(None)

    def publish(self, agent_queue_event: AgentQueueEvent) -> None:
        """Publish an event to the queue."""
        # 1. Add the event to the internal queue
        self.q.put(agent_queue_event)

        # 2. If the event type indicates a stop condition, stop listening
        if agent_queue_event.event in [
            QueueEvent.STOP,
            QueueEvent.ERROR,
            QueueEvent.TIMEOUT,
            QueueEvent.AGENT_END,
        ]:
            self.stop_listen()

    def publish_error(self, error) -> None:
        """Publish an error event to the queue."""
        self.publish(
            AgentQueueEvent(
                id=uuid.uuid4(),
                task_id=self.task_id,
                event=QueueEvent.ERROR,
                observation=str(error),
            )
        )

    def _is_stopped(self) -> bool:
        """Check whether the current task has been stopped."""
        task_stopped_cache_key = self.generate_task_stopped_cache_key(self.task_id)
        result = self.redis_client.get(task_stopped_cache_key)
        return result is not None

    @classmethod
    def generate_task_belong_cache_key(cls, task_id: UUID) -> str:
        """Generate a cache key indicating which account this task belongs to."""
        return f"generate_task_belong:{str(task_id)}"

    @classmethod
    def generate_task_stopped_cache_key(cls, task_id: UUID) -> str:
        """Generate a cache key that marks the task as stopped."""
        return f"generate_task_stopped:{str(task_id)}"
