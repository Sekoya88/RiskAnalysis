"""
Backward-compatible shim — re-exports from new DDD locations.
"""

from src.application.supervisor import supervisor_node, REQUIRED_PIPELINE, AGENT_OPTIONS

__all__ = ["supervisor_node", "REQUIRED_PIPELINE", "AGENT_OPTIONS"]
