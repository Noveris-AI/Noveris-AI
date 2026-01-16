"""
WebSocket Endpoints for Real-time Event Streaming.

Provides WebSocket connections for:
- Job run events (Ansible execution progress)
- Node status updates
- System notifications
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, Optional, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, HTTPException
from redis.asyncio import Redis
import structlog

from app.core.config import settings
from app.core.dependencies import get_redis
from app.services.node_management.job_queue_service import JobQueueService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/ws", tags=["WebSocket"])


class ConnectionManager:
    """Manage WebSocket connections for event streaming."""

    def __init__(self):
        # job_run_id -> set of websocket connections
        self.job_connections: Dict[str, Set[WebSocket]] = {}
        # node_id -> set of websocket connections
        self.node_connections: Dict[str, Set[WebSocket]] = {}
        # All system event connections
        self.system_connections: Set[WebSocket] = set()

    async def connect_job(self, websocket: WebSocket, job_run_id: str):
        """Connect a client to job events."""
        await websocket.accept()
        if job_run_id not in self.job_connections:
            self.job_connections[job_run_id] = set()
        self.job_connections[job_run_id].add(websocket)
        logger.info("WebSocket connected to job", job_run_id=job_run_id)

    async def disconnect_job(self, websocket: WebSocket, job_run_id: str):
        """Disconnect a client from job events."""
        if job_run_id in self.job_connections:
            self.job_connections[job_run_id].discard(websocket)
            if not self.job_connections[job_run_id]:
                del self.job_connections[job_run_id]
        logger.info("WebSocket disconnected from job", job_run_id=job_run_id)

    async def connect_node(self, websocket: WebSocket, node_id: str):
        """Connect a client to node events."""
        await websocket.accept()
        if node_id not in self.node_connections:
            self.node_connections[node_id] = set()
        self.node_connections[node_id].add(websocket)
        logger.info("WebSocket connected to node", node_id=node_id)

    async def disconnect_node(self, websocket: WebSocket, node_id: str):
        """Disconnect a client from node events."""
        if node_id in self.node_connections:
            self.node_connections[node_id].discard(websocket)
            if not self.node_connections[node_id]:
                del self.node_connections[node_id]
        logger.info("WebSocket disconnected from node", node_id=node_id)

    async def broadcast_job_event(self, job_run_id: str, event: dict):
        """Broadcast an event to all clients watching a job."""
        if job_run_id in self.job_connections:
            dead_connections = set()
            for websocket in self.job_connections[job_run_id]:
                try:
                    await websocket.send_json(event)
                except Exception:
                    dead_connections.add(websocket)
            # Clean up dead connections
            for dead in dead_connections:
                self.job_connections[job_run_id].discard(dead)

    async def broadcast_node_event(self, node_id: str, event: dict):
        """Broadcast an event to all clients watching a node."""
        if node_id in self.node_connections:
            dead_connections = set()
            for websocket in self.node_connections[node_id]:
                try:
                    await websocket.send_json(event)
                except Exception:
                    dead_connections.add(websocket)
            # Clean up dead connections
            for dead in dead_connections:
                self.node_connections[node_id].discard(dead)


# Global connection manager
manager = ConnectionManager()


@router.websocket("/jobs/{job_run_id}/events")
async def websocket_job_events(
    websocket: WebSocket,
    job_run_id: str,
    include_history: bool = Query(True, description="Include past events on connect")
):
    """
    WebSocket endpoint for streaming job run events.

    Connect to receive real-time Ansible execution events:
    - task_start, task_ok, task_failed
    - play_start, playbook_on_stats
    - runner_on_unreachable, etc.

    Query params:
        include_history: If true, sends all existing events on connect
    """
    try:
        job_uuid = uuid.UUID(job_run_id)
    except ValueError:
        await websocket.close(code=4000, reason="Invalid job_run_id format")
        return

    # Get Redis connection from app state
    try:
        redis: Redis = websocket.app.state.redis
    except AttributeError:
        # Fallback: create a new Redis connection
        from app.core.database import get_redis_pool
        redis = await get_redis_pool()

    await manager.connect_job(websocket, job_run_id)

    try:
        # Send connection confirmation
        await websocket.send_json({
            "type": "connected",
            "job_run_id": job_run_id,
            "timestamp": datetime.utcnow().isoformat()
        })

        # Get job queue service
        job_queue = JobQueueService(redis)

        # Send historical events if requested
        if include_history:
            events = await job_queue.get_job_events(job_run_id, start=0, count=1000)
            for event in events:
                await websocket.send_json({
                    "type": "event",
                    "event": event
                })
            await websocket.send_json({
                "type": "history_complete",
                "count": len(events)
            })

        # Subscribe to real-time events via Redis PubSub
        pubsub = redis.pubsub()
        channel = f"job_events:{job_run_id}"

        try:
            await pubsub.subscribe(channel)

            # Listen for events
            while True:
                try:
                    message = await asyncio.wait_for(
                        pubsub.get_message(ignore_subscribe_messages=True),
                        timeout=30.0
                    )

                    if message and message["type"] == "message":
                        try:
                            event_data = json.loads(message["data"])
                            await websocket.send_json({
                                "type": "event",
                                "event": event_data
                            })

                            # Check if job is complete
                            if event_data.get("event_type") in ["playbook_on_stats", "runner_on_failed"]:
                                await websocket.send_json({
                                    "type": "job_complete",
                                    "job_run_id": job_run_id,
                                    "timestamp": datetime.utcnow().isoformat()
                                })
                        except json.JSONDecodeError:
                            continue

                    # Send heartbeat on timeout
                    if message is None:
                        await websocket.send_json({
                            "type": "heartbeat",
                            "timestamp": datetime.utcnow().isoformat()
                        })

                except asyncio.TimeoutError:
                    # Send heartbeat
                    await websocket.send_json({
                        "type": "heartbeat",
                        "timestamp": datetime.utcnow().isoformat()
                    })

        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()

    except WebSocketDisconnect:
        logger.info("Client disconnected from job events", job_run_id=job_run_id)
    except Exception as e:
        logger.error("WebSocket error", job_run_id=job_run_id, error=str(e))
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except Exception:
            pass
    finally:
        await manager.disconnect_job(websocket, job_run_id)


@router.websocket("/jobs/all")
async def websocket_all_job_events(websocket: WebSocket):
    """
    WebSocket endpoint for streaming all job events.

    Useful for dashboard displays showing all running jobs.
    """
    try:
        redis: Redis = websocket.app.state.redis
    except AttributeError:
        from app.core.database import get_redis_pool
        redis = await get_redis_pool()

    await websocket.accept()

    try:
        await websocket.send_json({
            "type": "connected",
            "channel": "all_jobs",
            "timestamp": datetime.utcnow().isoformat()
        })

        pubsub = redis.pubsub()
        # Subscribe to pattern for all job events
        await pubsub.psubscribe("job_events:*")

        try:
            while True:
                try:
                    message = await asyncio.wait_for(
                        pubsub.get_message(ignore_subscribe_messages=True),
                        timeout=30.0
                    )

                    if message and message["type"] == "pmessage":
                        try:
                            # Extract job_run_id from channel
                            channel = message["channel"]
                            if isinstance(channel, bytes):
                                channel = channel.decode()
                            job_run_id = channel.split(":")[-1]

                            event_data = json.loads(message["data"])
                            await websocket.send_json({
                                "type": "event",
                                "job_run_id": job_run_id,
                                "event": event_data
                            })
                        except (json.JSONDecodeError, IndexError):
                            continue

                    if message is None:
                        await websocket.send_json({
                            "type": "heartbeat",
                            "timestamp": datetime.utcnow().isoformat()
                        })

                except asyncio.TimeoutError:
                    await websocket.send_json({
                        "type": "heartbeat",
                        "timestamp": datetime.utcnow().isoformat()
                    })

        finally:
            await pubsub.punsubscribe("job_events:*")
            await pubsub.close()

    except WebSocketDisconnect:
        logger.info("Client disconnected from all job events")
    except Exception as e:
        logger.error("WebSocket error", error=str(e))


@router.websocket("/nodes/{node_id}/status")
async def websocket_node_status(
    websocket: WebSocket,
    node_id: str
):
    """
    WebSocket endpoint for streaming node status updates.

    Receive real-time updates when:
    - Node status changes (READY, UNREACHABLE, etc.)
    - Connectivity verification completes
    - Facts collection updates node info
    """
    try:
        node_uuid = uuid.UUID(node_id)
    except ValueError:
        await websocket.close(code=4000, reason="Invalid node_id format")
        return

    try:
        redis: Redis = websocket.app.state.redis
    except AttributeError:
        from app.core.database import get_redis_pool
        redis = await get_redis_pool()

    await manager.connect_node(websocket, node_id)

    try:
        await websocket.send_json({
            "type": "connected",
            "node_id": node_id,
            "timestamp": datetime.utcnow().isoformat()
        })

        pubsub = redis.pubsub()
        channel = f"node_status:{node_id}"

        try:
            await pubsub.subscribe(channel)

            while True:
                try:
                    message = await asyncio.wait_for(
                        pubsub.get_message(ignore_subscribe_messages=True),
                        timeout=30.0
                    )

                    if message and message["type"] == "message":
                        try:
                            status_data = json.loads(message["data"])
                            await websocket.send_json({
                                "type": "status_update",
                                "node_id": node_id,
                                "data": status_data
                            })
                        except json.JSONDecodeError:
                            continue

                    if message is None:
                        await websocket.send_json({
                            "type": "heartbeat",
                            "timestamp": datetime.utcnow().isoformat()
                        })

                except asyncio.TimeoutError:
                    await websocket.send_json({
                        "type": "heartbeat",
                        "timestamp": datetime.utcnow().isoformat()
                    })

        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()

    except WebSocketDisconnect:
        logger.info("Client disconnected from node status", node_id=node_id)
    except Exception as e:
        logger.error("WebSocket error", node_id=node_id, error=str(e))
    finally:
        await manager.disconnect_node(websocket, node_id)


# Export the manager for use by other services
def get_connection_manager() -> ConnectionManager:
    """Get the global connection manager."""
    return manager
