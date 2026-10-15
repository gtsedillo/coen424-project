"""The decision-maker inside v2.

Week 7 (this file): PlaceholderAgent, a stand-in with the same interface the
Gemini agent will have. It lets us build and test everything around the agent
(server, deadline, validator, fallback, logging, Docker) before the cloud
project exists. It is NOT the AI part of the project.

Week 8: GeminiAgent replaces it. Gemini receives the request plus a list of
tools (get_product, list_by_category, get_history), decides which to call, and
returns product IDs. Only `recommend` and AgentResult need to stay the same.

FAULT_MODE injects failures on purpose, for tests and for the rollback demo:
  none         normal behaviour
  invalid_ids  return an ID that does not exist (caught by the validator)
  slow         sleep past the deadline (caught by the timeout)
  error        raise an exception
"""

import time
from dataclasses import dataclass, field

FAULT_MODES = ("none", "invalid_ids", "slow", "error")


class AgentError(Exception):
    pass


@dataclass
class AgentResult:
    product_ids: list
    tool_calls: list = field(default_factory=list)
    model: str = "none"
    input_tokens: int = 0
    output_tokens: int = 0


class PlaceholderAgent:
    """Prefers products that share a category with the requested ones."""

    name = "placeholder"

    def __init__(self, fault_mode="none", slow_seconds=10.0, max_results=5):
        if fault_mode not in FAULT_MODES:
            raise ValueError(f"FAULT_MODE must be one of {FAULT_MODES}, got {fault_mode!r}")
        self.fault_mode = fault_mode
        self.slow_seconds = slow_seconds
        self.max_results = max_results

    def recommend(self, user_id, product_ids, catalog):
        if self.fault_mode == "error":
            raise AgentError("injected fault: error")
        if self.fault_mode == "slow":
            time.sleep(self.slow_seconds)

        products = catalog.list_products()
        tool_calls = ["list_products"]
        requested = set(product_ids)
        wanted_categories = {
            category
            for product in products
            if product.id in requested
            for category in product.categories
        }

        def score(product):
            shared = len(wanted_categories & set(product.categories))
            return (-shared, product.name)  # most shared categories first, then by name

        candidates = sorted((p for p in products if p.id not in requested), key=score)
        chosen = [p.id for p in candidates[: self.max_results]]

        if self.fault_mode == "invalid_ids" and chosen:
            chosen[-1] = "NOT_A_PRODUCT"

        return AgentResult(product_ids=chosen, tool_calls=tool_calls, model=self.name)
