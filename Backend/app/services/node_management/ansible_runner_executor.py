"""
Ansible Runner Job Executor.

Executes Ansible playbooks using ansible-runner library.
Supports:
- Async job execution from Redis queue
- Real-time event streaming
- Artifact collection and storage
- Job cancellation
- Windows (WinRM) and Linux (SSH) targets
"""

import asyncio
import json
import os
import shutil
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Awaitable
import signal

import structlog
from redis.asyncio import Redis

from app.core.config import settings
from app.models.node import JobStatus
from app.services.node_management.job_queue_service import JobQueueService

logger = structlog.get_logger(__name__)


class AnsibleExecutionError(Exception):
    """Error during Ansible execution."""
    pass


class JobCancelledError(Exception):
    """Job was cancelled."""
    pass


class AnsibleRunnerExecutor:
    """
    Ansible Runner based job executor.

    Executes Ansible playbooks and streams events back to Redis.
    Supports both synchronous and asynchronous execution patterns.
    """

    def __init__(
        self,
        worker_id: str,
        redis_client: Redis,
        playbooks_dir: Optional[str] = None,
        work_dir: Optional[str] = None,
    ):
        self.worker_id = worker_id
        self.redis = redis_client
        self.playbooks_dir = Path(playbooks_dir or settings.ansible.playbooks_dir)
        self.work_dir = Path(work_dir or settings.ansible.work_dir)
        self.job_queue = JobQueueService(redis_client)

        # Ensure directories exist
        self.work_dir.mkdir(parents=True, exist_ok=True)

        # Track running processes for cancellation
        self._running_jobs: Dict[str, asyncio.subprocess.Process] = {}
        self._shutdown_event = asyncio.Event()

    async def start_worker(self, concurrency: int = 1):
        """
        Start the worker loop to process jobs from queue.

        Args:
            concurrency: Number of concurrent jobs to process
        """
        logger.info(
            "Starting Ansible runner worker",
            worker_id=self.worker_id,
            concurrency=concurrency
        )

        # Handle shutdown signals
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(
                sig,
                lambda s=sig: asyncio.create_task(self._handle_shutdown(s))
            )

        # Start worker tasks
        workers = [
            asyncio.create_task(self._worker_loop(i))
            for i in range(concurrency)
        ]

        try:
            await asyncio.gather(*workers, return_exceptions=True)
        except asyncio.CancelledError:
            logger.info("Worker tasks cancelled")
        finally:
            logger.info("Worker shutdown complete", worker_id=self.worker_id)

    async def _handle_shutdown(self, sig):
        """Handle shutdown signal."""
        logger.info("Received shutdown signal", signal=sig)
        self._shutdown_event.set()

        # Cancel all running jobs
        for job_id, process in list(self._running_jobs.items()):
            logger.info("Terminating running job", job_id=job_id)
            process.terminate()

    async def _worker_loop(self, worker_num: int):
        """Main worker loop that processes jobs from queue."""
        queue_name = settings.job_runner.queue_name

        while not self._shutdown_event.is_set():
            try:
                # Block-pop from queue with timeout
                result = await self.redis.blpop(queue_name, timeout=5)

                if result is None:
                    # Timeout, check for shutdown and continue
                    continue

                _, job_data = result
                job_info = json.loads(job_data)

                job_run_id = job_info.get("job_run_id")
                logger.info(
                    "Processing job",
                    job_run_id=job_run_id,
                    worker_num=worker_num
                )

                try:
                    await self.execute_job(job_info)
                except JobCancelledError:
                    logger.info("Job cancelled", job_run_id=job_run_id)
                except Exception as e:
                    logger.error(
                        "Job execution failed",
                        job_run_id=job_run_id,
                        error=str(e)
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Worker loop error", error=str(e))
                await asyncio.sleep(1)  # Back off on errors

    async def execute_job(self, job_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a single Ansible job.

        Args:
            job_info: Job configuration from queue

        Returns:
            Execution result with status and summary
        """
        job_run_id = job_info["job_run_id"]
        tenant_id = job_info.get("tenant_id")

        # Create temporary working directory
        job_work_dir = self.work_dir / "runs" / job_run_id
        job_work_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Update status to RUNNING
            await self._update_job_status(job_run_id, JobStatus.RUNNING)
            await self._publish_event(job_run_id, "job_started", {
                "worker_id": self.worker_id,
                "started_at": datetime.utcnow().isoformat()
            })

            # Write inventory file
            inventory_path = job_work_dir / "inventory.yml"
            inventory_path.write_text(job_info.get("inventory_content", ""))

            # Write extra vars file
            extra_vars = job_info.get("extra_vars", {})
            extra_vars_path = job_work_dir / "extravars.yml"
            import yaml
            extra_vars_path.write_text(yaml.dump(extra_vars))

            # Determine playbook path
            playbook_path = job_info.get("playbook_path", "")
            if not playbook_path.startswith("/"):
                playbook_path = str(self.playbooks_dir / playbook_path)

            # Build ansible-playbook command
            cmd = await self._build_ansible_command(
                playbook_path=playbook_path,
                inventory_path=str(inventory_path),
                extra_vars_path=str(extra_vars_path),
                job_info=job_info,
                work_dir=job_work_dir
            )

            # Execute with timeout
            timeout = job_info.get("timeout_seconds", 3600)
            result = await self._run_ansible_command(
                cmd=cmd,
                job_run_id=job_run_id,
                work_dir=job_work_dir,
                timeout=timeout
            )

            # Process results
            status = JobStatus.SUCCEEDED if result["rc"] == 0 else JobStatus.FAILED
            await self._update_job_status(job_run_id, status)

            # Collect artifacts
            artifacts = await self._collect_artifacts(
                job_run_id=job_run_id,
                work_dir=job_work_dir,
                bucket=job_info.get("artifacts_bucket"),
                prefix=job_info.get("artifacts_prefix")
            )

            await self._publish_event(job_run_id, "job_completed", {
                "status": status.value,
                "return_code": result["rc"],
                "summary": result.get("summary", {}),
                "finished_at": datetime.utcnow().isoformat(),
                "artifacts": artifacts
            })

            return {
                "status": status.value,
                "return_code": result["rc"],
                "summary": result.get("summary", {}),
                "artifacts": artifacts
            }

        except asyncio.TimeoutError:
            await self._update_job_status(job_run_id, JobStatus.FAILED)
            await self._publish_event(job_run_id, "job_timeout", {
                "message": f"Job exceeded timeout of {job_info.get('timeout_seconds')} seconds"
            })
            raise AnsibleExecutionError("Job execution timeout")

        except JobCancelledError:
            await self._update_job_status(job_run_id, JobStatus.CANCELED)
            raise

        except Exception as e:
            await self._update_job_status(job_run_id, JobStatus.FAILED)
            await self._publish_event(job_run_id, "job_error", {
                "error": str(e),
                "failed_at": datetime.utcnow().isoformat()
            })
            raise

        finally:
            # Cleanup job from running jobs
            self._running_jobs.pop(job_run_id, None)

            # Cleanup work directory (optional - keep for debugging)
            if settings.ansible.cleanup_work_dir:
                shutil.rmtree(job_work_dir, ignore_errors=True)

    async def _build_ansible_command(
        self,
        playbook_path: str,
        inventory_path: str,
        extra_vars_path: str,
        job_info: Dict[str, Any],
        work_dir: Path
    ) -> List[str]:
        """Build the ansible-playbook command."""
        cmd = [
            "ansible-playbook",
            playbook_path,
            "-i", inventory_path,
            "-e", f"@{extra_vars_path}",
            "-v",  # Verbose output
        ]

        # Privilege escalation
        template = job_info.get("template_snapshot", {})
        if job_info.get("become") or template.get("become"):
            cmd.append("--become")
            become_method = job_info.get("become_method") or template.get("become_method", "sudo")
            become_user = job_info.get("become_user") or template.get("become_user", "root")
            cmd.extend(["--become-method", become_method])
            cmd.extend(["--become-user", become_user])

        # Serial/batch execution for rolling updates
        serial = job_info.get("serial")
        if serial:
            # Serial is handled in playbook, but we can add forks limit
            cmd.extend(["--forks", "1"])

        # Add custom ansible.cfg if exists
        ansible_cfg = self.playbooks_dir / "ansible.cfg"
        if ansible_cfg.exists():
            os.environ["ANSIBLE_CONFIG"] = str(ansible_cfg)

        # Environment for better Windows support
        env_vars = {
            "ANSIBLE_HOST_KEY_CHECKING": "False",
            "ANSIBLE_STDOUT_CALLBACK": "json",  # JSON output for parsing
            "ANSIBLE_CALLBACKS_ENABLED": "profile_tasks",
            "ANSIBLE_RETRY_FILES_ENABLED": "False",
        }

        for key, value in env_vars.items():
            os.environ[key] = value

        return cmd

    async def _run_ansible_command(
        self,
        cmd: List[str],
        job_run_id: str,
        work_dir: Path,
        timeout: int
    ) -> Dict[str, Any]:
        """Execute ansible-playbook command and stream output."""
        logger.info(
            "Executing ansible command",
            job_run_id=job_run_id,
            command=" ".join(cmd)
        )

        stdout_path = work_dir / "stdout.txt"
        stderr_path = work_dir / "stderr.txt"

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(work_dir)
        )

        # Track running process for cancellation
        self._running_jobs[job_run_id] = process

        # Stream output with timeout
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )

            # Save output to files
            stdout_path.write_bytes(stdout)
            stderr_path.write_bytes(stderr)

            # Parse JSON output if available
            summary = {}
            try:
                if stdout:
                    output_data = json.loads(stdout.decode())
                    summary = self._parse_ansible_output(output_data)
            except (json.JSONDecodeError, Exception):
                # Fallback to basic parsing
                summary = {
                    "stdout_lines": len(stdout.decode().splitlines()) if stdout else 0,
                    "stderr_lines": len(stderr.decode().splitlines()) if stderr else 0,
                }

            return {
                "rc": process.returncode,
                "stdout": stdout.decode() if stdout else "",
                "stderr": stderr.decode() if stderr else "",
                "summary": summary
            }

        except asyncio.CancelledError:
            process.terminate()
            await process.wait()
            raise JobCancelledError("Job cancelled by user")

    def _parse_ansible_output(self, output: Dict) -> Dict[str, Any]:
        """Parse Ansible JSON output into summary."""
        stats = output.get("stats", {})

        summary = {
            "hosts": {},
            "total_tasks": 0,
            "ok": 0,
            "changed": 0,
            "failures": 0,
            "skipped": 0,
            "unreachable": 0,
        }

        for host, host_stats in stats.items():
            summary["hosts"][host] = host_stats
            summary["ok"] += host_stats.get("ok", 0)
            summary["changed"] += host_stats.get("changed", 0)
            summary["failures"] += host_stats.get("failures", 0)
            summary["skipped"] += host_stats.get("skipped", 0)
            summary["unreachable"] += host_stats.get("unreachable", 0)

        # Get plays info
        plays = output.get("plays", [])
        for play in plays:
            tasks = play.get("tasks", [])
            summary["total_tasks"] += len(tasks)

        return summary

    async def _collect_artifacts(
        self,
        job_run_id: str,
        work_dir: Path,
        bucket: Optional[str],
        prefix: Optional[str]
    ) -> Dict[str, Any]:
        """Collect and optionally upload job artifacts."""
        artifacts = {
            "stdout": str(work_dir / "stdout.txt"),
            "stderr": str(work_dir / "stderr.txt"),
            "inventory": str(work_dir / "inventory.yml"),
        }

        # TODO: Implement S3/GCS upload if bucket is configured
        # For now, just return local paths

        return {
            "local_paths": artifacts,
            "bucket": bucket,
            "prefix": prefix,
            "uploaded": False  # Would be True after S3 upload
        }

    async def _update_job_status(self, job_run_id: str, status: JobStatus):
        """Update job status in Redis."""
        await self.redis.hset(
            f"job_status:{job_run_id}",
            mapping={
                "status": status.value,
                "updated_at": datetime.utcnow().isoformat(),
                "worker_id": self.worker_id
            }
        )

    async def _publish_event(
        self,
        job_run_id: str,
        event_type: str,
        payload: Dict[str, Any]
    ):
        """Publish job event to Redis PubSub."""
        event = {
            "job_run_id": job_run_id,
            "event_type": event_type,
            "payload": payload,
            "timestamp": datetime.utcnow().isoformat(),
            "worker_id": self.worker_id
        }
        channel = f"job_events:{job_run_id}"
        await self.redis.publish(channel, json.dumps(event))


class AnsibleRunnerWithAnsibleRunner(AnsibleRunnerExecutor):
    """
    Enhanced executor using the ansible-runner Python library.

    Provides more control over execution including:
    - Proper event handling and streaming
    - Better artifact management
    - Built-in timeout handling
    - Role/collection support
    """

    async def execute_with_ansible_runner(
        self,
        job_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute using ansible-runner library."""
        try:
            import ansible_runner
        except ImportError:
            logger.warning("ansible-runner not installed, using subprocess fallback")
            return await self.execute_job(job_info)

        job_run_id = job_info["job_run_id"]
        job_work_dir = self.work_dir / "runs" / job_run_id
        job_work_dir.mkdir(parents=True, exist_ok=True)

        # Prepare ansible-runner directory structure
        project_dir = job_work_dir / "project"
        inventory_dir = job_work_dir / "inventory"
        env_dir = job_work_dir / "env"

        project_dir.mkdir(exist_ok=True)
        inventory_dir.mkdir(exist_ok=True)
        env_dir.mkdir(exist_ok=True)

        try:
            # Write inventory
            (inventory_dir / "hosts.yml").write_text(
                job_info.get("inventory_content", "")
            )

            # Write extra vars
            import yaml
            (env_dir / "extravars").write_text(
                yaml.dump(job_info.get("extra_vars", {}))
            )

            # Write settings
            settings_data = {
                "idle_timeout": 30,
                "job_timeout": job_info.get("timeout_seconds", 3600),
            }
            (env_dir / "settings").write_text(json.dumps(settings_data))

            # Determine playbook path
            playbook = job_info.get("playbook_path", "")
            if not playbook.startswith("/"):
                # Copy playbook to project dir
                src_playbook = self.playbooks_dir / playbook
                if src_playbook.exists():
                    shutil.copy(src_playbook, project_dir / Path(playbook).name)
                    playbook = Path(playbook).name

            # Update status
            await self._update_job_status(job_run_id, JobStatus.RUNNING)
            await self._publish_event(job_run_id, "job_started", {
                "worker_id": self.worker_id,
                "started_at": datetime.utcnow().isoformat()
            })

            # Event callback for streaming
            async def event_handler(event: Dict):
                await self._publish_event(
                    job_run_id,
                    event.get("event", "runner_event"),
                    event
                )

            # Run with ansible-runner
            loop = asyncio.get_event_loop()

            # Run in executor since ansible-runner is sync
            runner = await loop.run_in_executor(
                None,
                lambda: ansible_runner.run(
                    private_data_dir=str(job_work_dir),
                    playbook=playbook,
                    quiet=False,
                    json_mode=True,
                )
            )

            # Process results
            status = (
                JobStatus.SUCCEEDED if runner.status == "successful"
                else JobStatus.FAILED
            )

            await self._update_job_status(job_run_id, status)

            summary = {
                "status": runner.status,
                "rc": runner.rc,
                "stats": runner.stats,
            }

            await self._publish_event(job_run_id, "job_completed", {
                "status": status.value,
                "return_code": runner.rc,
                "summary": summary,
                "finished_at": datetime.utcnow().isoformat()
            })

            return {
                "status": status.value,
                "return_code": runner.rc,
                "summary": summary,
            }

        except Exception as e:
            await self._update_job_status(job_run_id, JobStatus.FAILED)
            await self._publish_event(job_run_id, "job_error", {
                "error": str(e)
            })
            raise


async def create_worker(
    worker_id: Optional[str] = None,
    redis_url: Optional[str] = None,
    concurrency: int = 1
):
    """
    Create and start an Ansible runner worker.

    Args:
        worker_id: Unique worker identifier (auto-generated if None)
        redis_url: Redis connection URL
        concurrency: Number of concurrent jobs

    Returns:
        AnsibleRunnerExecutor instance
    """
    from redis.asyncio import from_url

    worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
    redis_url = redis_url or settings.redis.url

    redis_client = await from_url(redis_url)

    executor = AnsibleRunnerExecutor(
        worker_id=worker_id,
        redis_client=redis_client,
    )

    await executor.start_worker(concurrency=concurrency)

    return executor


# CLI entry point
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ansible Runner Worker")
    parser.add_argument(
        "--worker-id",
        help="Unique worker identifier"
    )
    parser.add_argument(
        "--redis-url",
        help="Redis connection URL"
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="Number of concurrent jobs"
    )

    args = parser.parse_args()

    asyncio.run(create_worker(
        worker_id=args.worker_id,
        redis_url=args.redis_url,
        concurrency=args.concurrency
    ))
