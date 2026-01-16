"""
Async Job Queue Service for Node Management.

Provides async Redis-based job queue operations:
- Enqueue jobs for Ansible execution
- Cancel running jobs
- Query queue status
- Stream job events via WebSocket
"""

import json
import asyncio
from datetime import datetime
from typing import Any, Dict, Optional, List
from redis.asyncio import Redis
import structlog

from app.core.config import settings
from app.models.node import JobStatus

logger = structlog.get_logger(__name__)


class JobQueueService:
    """
    Async job queue service for managing Ansible job execution queue.

    Uses Redis for:
    - Job queue (list)
    - Job status tracking (hash)
    - Event streaming (PubSub)
    - Node locks (string with TTL)
    """

    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self.queue_name = settings.job_runner.queue_name
        self.events_prefix = "job_events:"
        self.status_prefix = "job_status:"
        self.lock_prefix = "node_lock:"

    async def enqueue_job(self, job_info: Dict[str, Any]) -> bool:
        """
        Add a job to the execution queue.

        Args:
            job_info: Job data containing:
                - job_run_id: Unique job ID
                - playbook_path: Path to Ansible playbook
                - inventory_content: YAML inventory content
                - extra_vars: Extra variables dict
                - target_node_ids: List of node IDs
                - template_snapshot: Template configuration
                - become: Privilege escalation settings
                - timeout_seconds: Job timeout

        Returns:
            True if enqueued successfully, False otherwise
        """
        try:
            job_run_id = job_info.get("job_run_id")
            if not job_run_id:
                logger.error("Cannot enqueue job without job_run_id")
                return False

            job_data = json.dumps(job_info)
            await self.redis.rpush(self.queue_name, job_data)

            # Initialize job status
            await self.redis.hset(
                f"{self.status_prefix}{job_run_id}",
                mapping={
                    "status": JobStatus.PENDING.value,
                    "enqueued_at": datetime.utcnow().isoformat(),
                }
            )
            # Set TTL for status (24 hours)
            await self.redis.expire(
                f"{self.status_prefix}{job_run_id}",
                settings.job_runner.result_ttl
            )

            logger.info(
                "Job enqueued",
                job_run_id=job_run_id,
                queue=self.queue_name
            )
            return True

        except Exception as e:
            logger.error("Failed to enqueue job", error=str(e))
            return False

    async def cancel_job(self, job_run_id: str, reason: str = None) -> bool:
        """
        Signal a job to be cancelled.

        Args:
            job_run_id: Job ID to cancel
            reason: Optional cancellation reason

        Returns:
            True if signal sent, False otherwise
        """
        try:
            cancel_data = json.dumps({
                "action": "cancel",
                "job_run_id": job_run_id,
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat()
            })
            await self.redis.publish("job_cancel_signals", cancel_data)

            logger.info("Job cancellation signaled", job_run_id=job_run_id)
            return True

        except Exception as e:
            logger.error("Failed to signal cancellation", error=str(e))
            return False

    async def get_queue_length(self) -> int:
        """Get the number of jobs waiting in the queue."""
        return await self.redis.llen(self.queue_name)

    async def get_job_status(self, job_run_id: str) -> Optional[Dict[str, str]]:
        """Get the current status of a job from Redis."""
        status_data = await self.redis.hgetall(f"{self.status_prefix}{job_run_id}")
        return status_data if status_data else None

    async def get_job_events(
        self,
        job_run_id: str,
        start: int = 0,
        count: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get job events from Redis list.

        Args:
            job_run_id: Job ID
            start: Starting index
            count: Number of events to fetch

        Returns:
            List of event dicts
        """
        events_key = f"{self.events_prefix}{job_run_id}"
        raw_events = await self.redis.lrange(events_key, start, start + count - 1)

        events = []
        for raw in raw_events:
            try:
                events.append(json.loads(raw))
            except json.JSONDecodeError:
                continue

        return events

    async def subscribe_to_events(self, job_run_id: str):
        """
        Subscribe to job events via PubSub.

        Yields event dicts as they arrive.
        """
        pubsub = self.redis.pubsub()
        channel = f"{self.events_prefix}{job_run_id}"

        try:
            await pubsub.subscribe(channel)

            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        yield json.loads(message["data"])
                    except json.JSONDecodeError:
                        continue
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()

    async def check_node_lock(self, node_id: str) -> Optional[str]:
        """
        Check if a node is locked by another job.

        Returns:
            Worker ID holding the lock, or None if unlocked
        """
        return await self.redis.get(f"{self.lock_prefix}{node_id}")

    async def get_queue_stats(self) -> Dict[str, Any]:
        """
        Get overall queue statistics.

        Returns:
            Dict with queue_length, active_jobs, etc.
        """
        queue_length = await self.get_queue_length()

        # Count jobs by status (scan status keys)
        status_counts = {
            "pending": 0,
            "running": 0,
        }

        cursor = 0
        while True:
            cursor, keys = await self.redis.scan(
                cursor,
                match=f"{self.status_prefix}*",
                count=100
            )

            for key in keys:
                status_data = await self.redis.hget(key, "status")
                if status_data:
                    status = status_data.lower()
                    if status in status_counts:
                        status_counts[status] += 1

            if cursor == 0:
                break

        return {
            "queue_length": queue_length,
            "pending_jobs": status_counts["pending"],
            "running_jobs": status_counts["running"],
        }


# Singleton instance
_job_queue_service: Optional[JobQueueService] = None


def get_job_queue_service(redis_client: Redis) -> JobQueueService:
    """Get or create the job queue service singleton."""
    global _job_queue_service
    if _job_queue_service is None:
        _job_queue_service = JobQueueService(redis_client)
    return _job_queue_service
