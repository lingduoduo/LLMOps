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

from internal.core.agent.entities.queue_entity import AgentThought, QueueEvent
from internal.entity.conversation_entity import InvokeFrom


class AgentQueueManager:
    """Agent queue manager"""
    user_id: UUID
    invoke_from: InvokeFrom
    redis_client: Redis
    _queues: dict[str, Queue]

    def __init__(
            self,
            user_id: UUID,
            invoke_from: InvokeFrom,
    ) -> None:
        """Constructor to initialize the AgentQueueManager"""
        # 1. Initialize basic data
        self.user_id = user_id
        self.invoke_from = invoke_from
        self._queues = {}

        # 2. Initialize redis_client internally
        from app.http.module import injector
        self.redis_client = injector.get(Redis)

    def listen(self, task_id: UUID) -> Generator:
        """Listen to the queue and stream generated data"""
        # 1. Define timeout, start time, and last ping time
        listen_timeout = 600
        start_time = time.time()
        last_ping_time = 0

        # 2. Loop to continuously read data from the queue until timeout or completion
        while True:
            try:
                # 3. Get data from the queue; if it exists, yield it
                item = self.queue(task_id).get(timeout=1)
                if item is None:
                    break
                yield item
            except queue.Empty:
                continue
            finally:
                # 4. Compute elapsed time
                elapsed_time = time.time() - start_time

                # 5. Send a PING event every 10 seconds
                if elapsed_time // 10 > last_ping_time:
                    self.publish(task_id, AgentThought(
                        id=uuid.uuid4(),
                        task_id=task_id,
                        event=QueueEvent.PING,
                    ))
                    last_ping_time = elapsed_time // 10

                # 6. If total time exceeds timeout, publish TIMEOUT event
                if elapsed_time >= listen_timeout:
                    self.publish(task_id, AgentThought(
                        id=uuid.uuid4(),
                        task_id=task_id,
                        event=QueueEvent.TIMEOUT,
                    ))

                # 7. Check if the task has been stopped; if so, publish STOP event
                if self._is_stopped(task_id):
                    self.publish(task_id, AgentThought(
                        id=uuid.uuid4(),
                        task_id=task_id,
                        event=QueueEvent.STOP,
                    ))

    def stop_listen(self, task_id: UUID) -> None:
        """Stop listening to a queue"""
        self.queue(task_id).put(None)

    def publish(self, task_id: UUID, agent_thought: AgentThought) -> None:
        """Publish an event to the queue"""
        # 1. Put the event into the queue
        self.queue(task_id).put(agent_thought)

        # 2. If the event requires stopping (STOP, ERROR, TIMEOUT, AGENT_END), stop listening
        if agent_thought.event in [QueueEvent.STOP, QueueEvent.ERROR, QueueEvent.TIMEOUT, QueueEvent.AGENT_END]:
            self.stop_listen(task_id)

    def publish_error(self, task_id: UUID, error) -> None:
        """Publish an error event to the queue"""
        self.publish(task_id, AgentThought(
            id=uuid.uuid4(),
            task_id=task_id,
            event=QueueEvent.ERROR,
            observation=str(error),
        ))

    def _is_stopped(self, task_id: UUID) -> bool:
        """Check whether the task has been stopped"""
        task_stopped_cache_key = self.generate_task_stopped_cache_key(task_id)
        result = self.redis_client.get(task_stopped_cache_key)

        if result is not None:
            return True
        return False

    def queue(self, task_id: UUID) -> Queue:
        """Get or create the task queue for the given task_id"""
        # 1. Get the corresponding task queue from the internal dict
        q = self._queues.get(str(task_id))

        # 2. If the queue does not exist, create it and write a cache key
        if not q:
            # 3. Determine the user prefix for cache key
            user_prefix = "account" if self.invoke_from in [
                InvokeFrom.WEB_APP, InvokeFrom.DEBUGGER, InvokeFrom.ASSISTANT_AGENT,
            ] else "end-user"

            # 4. Set the cache key for this task, indicating it has started
            self.redis_client.setex(
                self.generate_task_belong_cache_key(task_id),
                1800,
                f"{user_prefix}-{str(self.user_id)}",
            )

            # 5. Create a new queue and store it in the dict
            q = Queue()
            self._queues[str(task_id)] = q

        return q

    @classmethod
    def set_stop_flag(cls, task_id: UUID, invoke_from: InvokeFrom, user_id: UUID) -> None:
        """Stop a session based on task_id + invoke_from + user_id"""
        # 1. Get redis_client
        from app.http.module import injector
        redis_client = injector.get(Redis)

        # 2. Get the task's cache key; if the task hasn't started, no need to stop
        result = redis_client.get(cls.generate_task_belong_cache_key(task_id))
        if not result:
            return

        # 3. Compute the expected cache value
        user_prefix = "account" if invoke_from in [
            InvokeFrom.WEB_APP, InvokeFrom.DEBUGGER, InvokeFrom.ASSISTANT_AGENT,
        ] else "end-user"
        if result.decode("utf-8") != f"{user_prefix}-{str(user_id)}":
            return

        # 4. Set the stop flag key
        stopped_cache_key = cls.generate_task_stopped_cache_key(task_id)
        redis_client.setex(stopped_cache_key, 600, 1)

    @classmethod
    def generate_task_belong_cache_key(cls, task_id: UUID) -> str:
        """Generate the cache key indicating which task this is"""
        return f"generate_task_belong:{str(task_id)}"

    @classmethod
    def generate_task_stopped_cache_key(cls, task_id: UUID) -> str:
        """Generate the cache key indicating the task has been stopped"""
        return f"generate_task_stopped:{str(task_id)}"
