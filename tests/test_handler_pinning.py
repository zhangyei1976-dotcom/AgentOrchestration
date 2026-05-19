"""Regression tests for handler pinning (Issue #8)."""

import pytest
from src.agent.registry import AgentRegistry, AgentStatus
from src.orchestrator.engine import OrchestrationEngine, ResolutionError


class TestHandlerPinning:
    """Verify that mid-run registry updates are detected and handled."""

    def test_registry_version_bumps_on_register(self):
        reg = AgentRegistry()
        v0 = reg.version
        reg.register("test", "worker.echo")
        assert reg.version == v0 + 1

    def test_registry_version_bumps_on_deregister(self):
        reg = AgentRegistry()
        agent_id = reg.register("test", "worker.echo")
        v_before = reg.version
        reg.deregister(agent_id)
        assert reg.version == v_before + 1
        assert reg.get(agent_id) is None

    def test_deregister_nonexistent_returns_false(self):
        reg = AgentRegistry()
        assert reg.deregister("nonexistent") is False

    def test_resolve_pinned_returns_agent_and_version(self):
        reg = AgentRegistry()
        agent_id = reg.register("test", "worker.echo")
        agent, version = reg.resolve_pinned(agent_id)
        assert agent is not None
        assert agent["name"] == "test"
        assert version == reg.version

    def test_resolve_pinned_detects_stale_registry(self):
        reg = AgentRegistry()
        agent_id = reg.register("test", "worker.echo")
        _, v1 = reg.resolve_pinned(agent_id)

        # Mutate registry
        reg.register("other", "worker.http")

        # Re-resolve with old version — should detect staleness
        agent, v2 = reg.resolve_pinned(agent_id, expected_version=v1)
        assert agent is None  # stale resolution
        assert v2 != v1

    def test_deregister_invalidates_pinned_handler(self):
        """Deregistering an agent mid-task must invalidate pins."""
        reg = AgentRegistry()
        agent_id = reg.register("test", "worker.echo")
        _, v1 = reg.resolve_pinned(agent_id)

        reg.deregister(agent_id)

        agent, v2 = reg.resolve_pinned(agent_id, expected_version=v1)
        assert agent is None
        assert v2 != v1
