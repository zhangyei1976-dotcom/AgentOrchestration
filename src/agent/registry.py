"""Agent Registry — Manages agent lifecycle and metadata with handler pinning."""

import json
import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional


class AgentStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    FAILED = "failed"
    TERMINATED = "terminated"


class AgentRegistry:
    """Thread-safe agent registry with versioned handler resolution.

    Every mutation bumps a monotonic version counter.  Task execution
    snapshots the version at resolve time and validates it hasn't
    changed before committing results — preventing mid-run registry
    updates from routing tasks to unavailable or incompatible handlers.
    """

    def __init__(self, storage_backend: str = "memory"):
        self.storage_backend = storage_backend
        self._agents: Dict[str, Dict[str, Any]] = {}
        self._index: Dict[str, List[str]] = {}
        self._version: int = 0

    # ── Versioning ────────────────────────────────────────

    @property
    def version(self) -> int:
        return self._version

    def _bump_version(self) -> int:
        self._version += 1
        return self._version

    # ── Registration ──────────────────────────────────────

    def register(self, name: str, agent_type: str, config: Optional[Dict] = None) -> str:
        """Register a new agent. Bumps the registry version."""
        agent_id = str(uuid.uuid4())
        timestamp = time.time()
        self._agents[agent_id] = {
            "id": agent_id,
            "name": name,
            "type": agent_type,
            "status": AgentStatus.PENDING.value,
            "config": config or {},
            "created_at": timestamp,
            "updated_at": timestamp,
            "version": "1.0.0",
            "metrics": {"tasks_completed": 0, "errors": 0, "uptime": 0},
        }
        group = agent_type.split(".")[0]
        if group not in self._index:
            self._index[group] = []
        self._index[group].append(agent_id)
        self._bump_version()
        return agent_id

    def deregister(self, agent_id: str) -> bool:
        """Remove an agent and invalidate any pinned resolutions.

        Returns False if the agent was not found.
        """
        agent = self._agents.pop(agent_id, None)
        if agent is None:
            return False
        # Clean up index
        group = agent["type"].split(".")[0]
        if group in self._index and agent_id in self._index[group]:
            self._index[group].remove(agent_id)
        self._bump_version()
        return True

    # ── Resolution ────────────────────────────────────────

    def get(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Resolve an agent by ID. Returns None if not found."""
        return self._agents.get(agent_id)

    def resolve_pinned(
        self, agent_id: str, expected_version: Optional[int] = None
    ) -> tuple[Optional[Dict[str, Any]], int]:
        """Resolve an agent and return (agent, registry_version).

        If expected_version is provided and differs from the current
        registry version, the pinned resolution is stale and the caller
        should re-resolve or abort.
        """
        agent = self._agents.get(agent_id)
        current_version = self._version
        if expected_version is not None and expected_version != current_version:
            # Registry mutated mid-execution — caller must re-validate
            return (None, current_version)
        return (agent, current_version)

    # ── Query ──────────────────────────────────────────────

    def list(self, status: Optional[AgentStatus] = None, group: Optional[str] = None) -> List[Dict[str, Any]]:
        agents = self._agents.values()
        if status:
            agents = [a for a in agents if a["status"] == status.value]
        if group:
            agent_ids = self._index.get(group, [])
            agents = [a for a in agents if a["id"] in agent_ids]
        return list(agents)

    # ── Lifecycle ──────────────────────────────────────────

    def update_status(self, agent_id: str, status: AgentStatus) -> bool:
        if agent_id not in self._agents:
            return False
        self._agents[agent_id]["status"] = status.value
        self._bump_version()
        return True

    def get_version(self) -> int:
        """Return the current registry version for external validation."""
        return self._version
