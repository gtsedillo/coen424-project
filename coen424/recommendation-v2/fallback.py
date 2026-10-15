"""v1's logic, kept as v2's safety net.

When the agent fails (error, timeout or invalid answer), v2 answers with the same
random selection v1 uses, so the shop keeps working. Every fallback is logged
and counted as a failure in the canary metrics, so it can never hide a bad v2.
"""

import random

from validator import MAX_RESULTS


def fallback_recommendations(catalog_ids, input_ids, max_results=MAX_RESULTS):
    """Same behaviour as v1: drop the requested IDs, pick up to 5 at random."""
    candidates = sorted(set(catalog_ids) - set(input_ids))
    return random.sample(candidates, min(max_results, len(candidates)))
