"""
Ansible Runner Worker.

Background worker that processes job runs from the Redis queue using ansible-runner.
Supports:
- Async execution with event streaming
- Job cancellation
- Artifact upload to MinIO
- Node-level mutex to prevent concurrent execution
"""

import asyncio
import json
import os
import signal
import shutil
import tempfile
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

import redis
import structlog
import yaml

from app.core.config import settings
from app.models.node import JobStatus

logger = structlog.get_logger(__name__)

# Try to import ansible_runner
try:
    import ansible_runner
    ANSIBLE_RUNNER_AVAILABLE = True
except ImportError:
    ANSIBLE_RUNNER_AVAILABLE = False
    logger.warning("ansible_runner not installed - job execution will be disabled")


class AnsibleRunnerWorker:
    """
    Worker that processes Ansible job runs from a Redis queue.

    Architecture:
    1. Polls Redis list for new job IDs
    2. Fetches job details from database
    3. Prepares ansible-runner private_data_dir
    4. Executes playbook with event handling
    5. Streams events to Redis PubSub for real-time logs
    6. Updates job status and uploads artifacts

    Supports horizontal scaling with node-level mutex locks.
    """

    def __init__(
        self,
        worker_id: Optional[str] = None,
        concurrency: int = None,
        db_dsn: str = None,
        redis_dsn: str = None,
        minio_config: Dict = None
    ):
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self.concurrency = concurrency or settings.job_runner.concurrency
        self.running = False
        self._current_jobs: Dict[str, threading.Thread] = {}
        self._cancel_flags: Dict[str, bool] = {}

        # Redis client
        self.redis = redis.from_url(redis_dsn or settings.redis.dsn)
        self.queue_name = settings.job_runner.queue_name
        self.events_prefix = "job_events:"
        self.lock_prefix = "node_lock:"

        # Working directories
        self.work_dir = Path(settings.ansible.work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)

        # Playbook paths
        self.playbook_repo = Path(settings.ansible.playbook_repo_path)

        logger.info(
            "AnsibleRunnerWorker initialized",
            worker_id=self.worker_id,
            concurrency=self.concurrency,
            queue=self.queue_name
        )

    def start(self):
        """Start the worker to process jobs from the queue."""
        if not ANSIBLE_RUNNER_AVAILABLE:
            logger.error("Cannot start worker - ansible_runner not installed")
            return

        self.running = True
        logger.info("Starting worker", worker_id=self.worker_id)

        # Register signal handlers
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

        while self.running:
            try:
                # Wait for new job from queue
                result = self.redis.blpop(self.queue_name, timeout=5)

                if result is None:
                    continue

                _, job_data = result
                job_info = json.loads(job_data)
                job_id = job_info.get("job_run_id")

                if not job_id:
                    logger.warning("Invalid job data received", data=job_data)
                    continue

                # Check concurrency limit
                active_count = len([t for t in self._current_jobs.values() if t.is_alive()])
                if active_count >= self.concurrency:
                    # Re-queue the job
                    self.redis.rpush(self.queue_name, job_data)
                    time.sleep(1)
                    continue

                # Start job in thread
                thread = threading.Thread(
                    target=self._execute_job,
                    args=(job_id, job_info),
                    daemon=True
                )
                self._current_jobs[job_id] = thread
                self._cancel_flags[job_id] = False
                thread.start()

            except redis.ConnectionError as e:
                logger.error("Redis connection error", error=str(e))
                time.sleep(5)
            except Exception as e:
                logger.error("Worker error", error=str(e))
                time.sleep(1)

    def stop(self):
        """Stop the worker gracefully."""
        logger.info("Stopping worker", worker_id=self.worker_id)
        self.running = False

        # Cancel all running jobs
        for job_id in list(self._cancel_flags.keys()):
            self._cancel_flags[job_id] = True

        # Wait for threads to finish
        for job_id, thread in list(self._current_jobs.items()):
            if thread.is_alive():
                thread.join(timeout=settings.job_runner.cancel_grace_period)

    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signals."""
        logger.info("Shutdown signal received", signal=signum)
        self.stop()

    def _execute_job(self, job_id: str, job_info: Dict[str, Any]):
        """Execute a single job run."""
        logger.info("Starting job execution", job_id=job_id)

        private_data_dir = None
        try:
            # Update status to RUNNING
            self._update_job_status(job_id, JobStatus.RUNNING)

            # Prepare private_data_dir
            private_data_dir = self._prepare_private_data_dir(job_info)

            # Get playbook path
            playbook_path = job_info.get("playbook_path", "bootstrap.yml")
            if not playbook_path.startswith("/"):
                playbook_path = str(self.playbook_repo / playbook_path)

            # Acquire node locks
            node_ids = job_info.get("target_node_ids", [])
            locks = self._acquire_node_locks(node_ids)

            try:
                # Execute using ansible-runner
                runner_config = {
                    "private_data_dir": str(private_data_dir),
                    "playbook": playbook_path,
                    "quiet": True,
                    "json_mode": True,
                    "event_handler": lambda e: self._handle_event(job_id, e),
                    "status_handler": lambda s, r: self._handle_status(job_id, s, r),
                    "cancel_callback": lambda: self._cancel_flags.get(job_id, False),
                }

                # Add extra vars
                extra_vars = job_info.get("extra_vars", {})
                if extra_vars:
                    runner_config["extravars"] = extra_vars

                # Add become settings
                if job_info.get("become", True):
                    runner_config["envvars"] = {
                        "ANSIBLE_BECOME": "true",
                        "ANSIBLE_BECOME_METHOD": job_info.get("become_method", "sudo"),
                        "ANSIBLE_BECOME_USER": job_info.get("become_user", "root"),
                    }

                # Run ansible-runner
                start_time = time.time()
                result = ansible_runner.run(**runner_config)
                duration = int(time.time() - start_time)

                # Process result
                if self._cancel_flags.get(job_id, False):
                    self._update_job_status(
                        job_id, JobStatus.CANCELED,
                        duration=duration
                    )
                elif result.status == "successful":
                    self._update_job_status(
                        job_id, JobStatus.SUCCEEDED,
                        summary=self._build_summary(result),
                        duration=duration
                    )
                else:
                    error_msg = self._extract_error(result)
                    self._update_job_status(
                        job_id, JobStatus.FAILED,
                        error_message=error_msg,
                        summary=self._build_summary(result),
                        duration=duration
                    )

            finally:
                # Release node locks
                self._release_node_locks(locks)

            # Upload artifacts
            self._upload_artifacts(job_id, private_data_dir, job_info)

        except Exception as e:
            logger.error("Job execution failed", job_id=job_id, error=str(e))
            self._update_job_status(
                job_id, JobStatus.FAILED,
                error_message=str(e)
            )
        finally:
            # Cleanup
            if private_data_dir and private_data_dir.exists():
                try:
                    shutil.rmtree(private_data_dir)
                except Exception as e:
                    logger.warning("Failed to cleanup", path=str(private_data_dir), error=str(e))

            # Remove from current jobs
            self._current_jobs.pop(job_id, None)
            self._cancel_flags.pop(job_id, None)

    def _prepare_private_data_dir(self, job_info: Dict[str, Any]) -> Path:
        """Prepare ansible-runner private_data_dir."""
        # Create unique directory
        run_id = job_info.get("job_run_id", uuid.uuid4().hex)
        private_data_dir = self.work_dir / f"run_{run_id}"
        private_data_dir.mkdir(parents=True, exist_ok=True)

        # Create required subdirectories
        (private_data_dir / "inventory").mkdir(exist_ok=True)
        (private_data_dir / "env").mkdir(exist_ok=True)
        (private_data_dir / "project").mkdir(exist_ok=True)

        # Write inventory
        inventory_content = job_info.get("inventory_content", "")
        if inventory_content:
            inventory_file = private_data_dir / "inventory" / "hosts.yml"
            inventory_file.write_text(inventory_content)

        # Write extra vars
        extra_vars = job_info.get("extra_vars", {})
        if extra_vars:
            extravars_file = private_data_dir / "env" / "extravars"
            extravars_file.write_text(yaml.dump(extra_vars))

        # Write SSH args
        settings_content = {
            "ssh_args": settings.ansible.ssh_args_default
        }
        settings_file = private_data_dir / "env" / "settings"
        settings_file.write_text(yaml.dump(settings_content))

        # Link playbooks
        project_link = private_data_dir / "project" / "playbooks"
        if not project_link.exists():
            try:
                project_link.symlink_to(self.playbook_repo)
            except OSError:
                # Copy instead of symlink if symlink fails
                shutil.copytree(self.playbook_repo, project_link)

        return private_data_dir

    def _handle_event(self, job_id: str, event: Dict[str, Any]):
        """Handle ansible-runner event."""
        # Publish to Redis for real-time streaming
        event_data = {
            "job_run_id": job_id,
            "ts": datetime.utcnow().isoformat(),
            "event": event
        }

        channel = f"{self.events_prefix}{job_id}"
        self.redis.publish(channel, json.dumps(event_data))

        # Store event (briefly) in Redis list for late subscribers
        self.redis.rpush(f"job_events_list:{job_id}", json.dumps(event_data))
        self.redis.expire(f"job_events_list:{job_id}", 3600)  # 1 hour

    def _handle_status(self, job_id: str, status: str, runner: Any):
        """Handle ansible-runner status changes."""
        logger.info("Job status changed", job_id=job_id, status=status)

    def _update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        summary: Dict = None,
        error_message: str = None,
        duration: int = None
    ):
        """Update job status in Redis (for quick access) and signal API to update DB."""
        status_data = {
            "job_run_id": job_id,
            "status": status.value,
            "updated_at": datetime.utcnow().isoformat(),
            "worker_id": self.worker_id,
        }

        if summary:
            status_data["summary"] = summary
        if error_message:
            status_data["error_message"] = error_message
        if duration is not None:
            status_data["duration_seconds"] = duration

        # Publish status update
        self.redis.publish("job_status_updates", json.dumps(status_data))

        # Store in Redis hash
        self.redis.hset(f"job_status:{job_id}", mapping={
            "status": status.value,
            "updated_at": datetime.utcnow().isoformat()
        })

    def _build_summary(self, result) -> Dict[str, int]:
        """Build execution summary from ansible-runner result."""
        stats = result.stats or {}
        summary = {
            "ok": 0,
            "changed": 0,
            "unreachable": 0,
            "failed": 0,
            "skipped": 0,
            "rescued": 0,
            "ignored": 0
        }

        for host, host_stats in stats.items():
            for key in summary:
                summary[key] += host_stats.get(key, 0)

        return summary

    def _extract_error(self, result) -> str:
        """Extract error message from failed result."""
        errors = []

        # Check for playbook errors in events
        for event in result.events:
            if event.get("event") == "runner_on_failed":
                event_data = event.get("event_data", {})
                task = event_data.get("task", "Unknown task")
                host = event_data.get("host", "Unknown host")
                res = event_data.get("res", {})
                msg = res.get("msg", res.get("stderr", "Unknown error"))
                errors.append(f"[{host}] {task}: {msg}")

        if errors:
            return "\n".join(errors[:5])  # Limit to 5 errors

        # Fallback
        if result.rc != 0:
            return f"Playbook failed with return code {result.rc}"

        return "Unknown error"

    def _acquire_node_locks(self, node_ids: List[str]) -> List[str]:
        """Acquire mutex locks for nodes to prevent concurrent execution."""
        locks = []
        for node_id in node_ids:
            lock_key = f"{self.lock_prefix}{node_id}"
            # Try to set lock with expiry
            if self.redis.set(lock_key, self.worker_id, nx=True, ex=3600):
                locks.append(lock_key)
            else:
                # Lock already held - wait or fail
                logger.warning(
                    "Node lock already held",
                    node_id=node_id,
                    holder=self.redis.get(lock_key)
                )
        return locks

    def _release_node_locks(self, locks: List[str]):
        """Release node mutex locks."""
        for lock_key in locks:
            # Only release if we hold the lock
            if self.redis.get(lock_key) == self.worker_id.encode():
                self.redis.delete(lock_key)

    def _upload_artifacts(
        self,
        job_id: str,
        private_data_dir: Path,
        job_info: Dict[str, Any]
    ):
        """Upload job artifacts to MinIO."""
        if not settings.minio.enabled:
            return

        try:
            from minio import Minio

            client = Minio(
                settings.minio.endpoint,
                access_key=settings.minio.access_key,
                secret_key=settings.minio.secret_key,
                secure=settings.minio.secure
            )

            bucket = job_info.get("artifacts_bucket", settings.node_management.artifacts_bucket)
            prefix = job_info.get("artifacts_prefix", f"jobs/{job_id}")

            # Ensure bucket exists
            if not client.bucket_exists(bucket):
                client.make_bucket(bucket)

            # Upload stdout
            stdout_file = private_data_dir / "artifacts" / "stdout"
            if stdout_file.exists():
                client.fput_object(
                    bucket,
                    f"{prefix}/stdout.txt",
                    str(stdout_file)
                )

            # Upload job_events.json
            events_file = private_data_dir / "artifacts" / "job_events.json"
            if events_file.exists():
                client.fput_object(
                    bucket,
                    f"{prefix}/job_events.json",
                    str(events_file)
                )

            # Upload status
            status_file = private_data_dir / "artifacts" / "status"
            if status_file.exists():
                client.fput_object(
                    bucket,
                    f"{prefix}/status.txt",
                    str(status_file)
                )

            logger.info("Artifacts uploaded", job_id=job_id, bucket=bucket, prefix=prefix)

        except Exception as e:
            logger.error("Failed to upload artifacts", job_id=job_id, error=str(e))


class JobQueuePublisher:
    """Publisher for adding jobs to the queue."""

    def __init__(self, redis_dsn: str = None):
        self.redis = redis.from_url(redis_dsn or settings.redis.dsn)
        self.queue_name = settings.job_runner.queue_name

    def enqueue_job(self, job_info: Dict[str, Any]) -> bool:
        """Add a job to the execution queue."""
        try:
            job_data = json.dumps(job_info)
            self.redis.rpush(self.queue_name, job_data)
            logger.info(
                "Job enqueued",
                job_run_id=job_info.get("job_run_id"),
                queue=self.queue_name
            )
            return True
        except Exception as e:
            logger.error("Failed to enqueue job", error=str(e))
            return False

    def cancel_job(self, job_id: str) -> bool:
        """Signal a job to be cancelled."""
        try:
            cancel_data = json.dumps({
                "action": "cancel",
                "job_run_id": job_id
            })
            self.redis.publish("job_cancel_signals", cancel_data)
            return True
        except Exception as e:
            logger.error("Failed to signal cancellation", error=str(e))
            return False

    def get_queue_length(self) -> int:
        """Get the number of jobs waiting in the queue."""
        return self.redis.llen(self.queue_name)


def run_worker():
    """Entry point for running the worker."""
    worker = AnsibleRunnerWorker()
    worker.start()


if __name__ == "__main__":
    run_worker()
