"""Task source loaders for 402Pilot-Bench.

Each loader pulls one public dataset (HumanEval / HotpotQA / TriviaQA-web /
OpenAssistant) and converts rows into ``Task`` objects with stable ids,
type labels, and heuristic difficulty estimates. A unified ``load_all_tasks``
combines all four sources in the proportions: 164 (all of HumanEval) +
220 + 220 + 220 = 824 tasks total.
"""

from pilot402.pregen.tasks.base import (
    TaskLoader,
    estimate_difficulty,
    is_cache_stale,
    read_cache,
    write_cache,
)
from pilot402.pregen.tasks.hotpotqa import HotpotQaLoader
from pilot402.pregen.tasks.humaneval import HumanEvalLoader
from pilot402.pregen.tasks.loader import DEFAULT_LIMITS, load_all_tasks
from pilot402.pregen.tasks.openweb import OpenWebLoader
from pilot402.pregen.tasks.triviaqa import TriviaQaLoader

__all__ = [
    "DEFAULT_LIMITS",
    "HotpotQaLoader",
    "HumanEvalLoader",
    "OpenWebLoader",
    "TaskLoader",
    "TriviaQaLoader",
    "estimate_difficulty",
    "is_cache_stale",
    "load_all_tasks",
    "read_cache",
    "write_cache",
]
