"""
Backward-compatible shim — re-exports from new DDD locations.

app.py imports set_log_queue and _extract_text from here.
The actual agent nodes are now in src/application/agents/.
"""

import queue

from src.domain.services.report_builder import extract_text as _extract_text
from src.application.agents.geopolitical import geopolitical_analyst_node
from src.application.agents.credit import credit_evaluator_node
from src.application.agents.synthesizer import market_synthesizer_node
from src.application.agents import geopolitical, credit, synthesizer


def set_log_queue(q: queue.Queue):
    """Set the shared log queue for all agent nodes."""
    from src.container import bootstrap, GEOPOLITICAL_TOOLS, CREDIT_TOOLS, SYNTHESIZER_TOOLS, get_memory_adapter
    bootstrap(log_queue=q)
    # Re-configure with the new queue
    geopolitical.configure(tools=GEOPOLITICAL_TOOLS, log_queue=q)
    credit.configure(tools=CREDIT_TOOLS, log_queue=q)
    synthesizer.configure(tools=SYNTHESIZER_TOOLS, memory_adapter=get_memory_adapter(), log_queue=q)


__all__ = [
    "_extract_text",
    "set_log_queue",
    "geopolitical_analyst_node",
    "credit_evaluator_node",
    "market_synthesizer_node",
]
