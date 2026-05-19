"""Orchestration Engine — Core execution with handler pinning."""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.agent import AgentRegistry, AgentStatus
from src.orchestrator.scheduler import TaskScheduler

logger = logging.getLogger(__name__)


class ResolutionError(Exception):
    """Raised when a pinned handler resolution becomes invalid."""


class OrchestrationEngine:
    def __init__(self, max_workers: int = 10, agent_timeout: int = 300):
        self.registry = AgentRegistry()
        self.scheduler = TaskScheduler()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.agent_timeout = agent_timeout
        self._running = False
        self._hooks: Dict[str, List[Callable]] = {
            "pre_execute": [],
            "post_execute": [],
            "on_error": [],
            "on_complete": [],
        }

    def register_hook(self, event: str, callback: Callable) -> None:
        if event in self._hooks:
            self._hooks[event].append(callback)

    async def start(self) -> None:
        self._running = True
        logger.info("Orchestration engine started")
        while self._running:
            task = await self.scheduler.dequeue()
            if task:
                asyncio.create_task(self._execute_task(task))
            await asyncio.sleep(0.1)

    def stop(self) -> None:
        self._running = False
        logger.info("Orchestration engine stopped")

    # ── Pinned Handler Resolution ─────────────────────────

    def _resolve_handler(
        self, agent_id: str
    ) -> Tuple[Dict[str, Any], int]:
        """Pin the resolved handler for this task attempt.

        Returns (agent_dict, registry_version_at_resolution_time).
        The version is used to detect mid-run registry mutations.
        """
        agent, version = self.registry.resolve_pinned(agent_id)
        if agent is None:
            raise ValueError(
                f"Agent {agent_id} not found in registry "
                f"(version {self.registry.version})"
            )
        logger.debug(
            "Handler pinned: agent=%s version=%d", agent_id, version
        )
        return agent, version

    def _validate_pinned(
        self, agent_id: str, pinned_version: int
    ) -> Dict[str, Any]:
        """Re-validate a pinned handler hasn't been invalidated.

        If the registry version has changed since resolution, the
        handler may have been deregistered or reconfigured.  We
        re-resolve and raise ResolutionError if the agent is gone.
        """
        if pinned_version != self.registry.version:
            logger.warning(
                "Registry mutated mid-run (v%d→v%d) — re-validating handler %s",
                pinned_version, self.registry.version, agent_id,
            )
            agent = self.registry.get(agent_id)
            if agent is None:
                raise ResolutionError(
                    f"Pinned handler {agent_id} was deregistered "
                    f"during task execution"
                )
            return agent
        return self.registry.get(agent_id)

    # ── Task Execution ─────────────────────────────────────

    async def _execute_task(self, task: Dict[str, Any]) -> None:
        task_id = task["id"]
        agent_id = task["target_agent"]
        logger.info(f"Executing task {task_id} on agent {agent_id}")

        for hook in self._hooks["pre_execute"]:
            await hook(task)

        # Pin handler resolution at task start
        try:
            agent, pinned_version = self._resolve_handler(agent_id)
        except ValueError as e:
            logger.error(f"Task {task_id}: {e}")
            for hook in self._hooks["on_error"]:
                await hook(task, e)
            return

        try:
            self.registry.update_status(agent_id, AgentStatus.RUNNING)

            # Re-validate pin before execution
            agent = self._validate_pinned(agent_id, pinned_version)

            result = await asyncio.wait_for(
                self._run_agent_task(agent, task),
                timeout=self.agent_timeout,
            )

            # Re-validate pin before committing
            self._validate_pinned(agent_id, pinned_version)
            self.registry.update_status(agent_id, AgentStatus.PAUSED)

            for hook in self._hooks["post_execute"]:
                await hook(task, result)

            logger.info(f"Task {task_id} completed successfully")

        except ResolutionError as e:
            logger.error(
                f"Task {task_id}: handler pin invalidated — %s", e
            )
            for hook in self._hooks["on_error"]:
                await hook(task, e)

        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            for hook in self._hooks["on_error"]:
                await hook(task, e)

    async def _run_agent_task(self, agent: Dict, task: Dict) -> Any:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self._execute_in_thread,
            agent,
            task,
        )

    def _execute_in_thread(self, agent: Dict, task: Dict) -> Any:
        return {
            "status": "completed",
            "output": f"Task {task['id']} processed by {agent['name']}",
        }
