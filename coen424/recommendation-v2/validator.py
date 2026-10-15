"""Correctness rules for a ListRecommendations response.

These are the rules from our canary criteria table. v1 is random, so we cannot
judge v2 by comparing it to v1; instead every v2 answer must satisfy all of:

  1. every returned ID exists in the product catalog;
  2. no ID from the request is returned;
  3. no duplicate IDs;
  4. between 1 and MAX_RESULTS IDs (0 is valid only when the catalog has
     nothing left to recommend).

Rule 1 matters most: the frontend looks up every returned ID, and a single
unknown ID makes it drop *all* recommendations (src/frontend/rpc.go).
"""

from dataclasses import dataclass, field

MAX_RESULTS = 5


@dataclass
class ValidationResult:
    valid: bool
    problems: list = field(default_factory=list)


def validate(output_ids, input_ids, catalog_ids, max_results=MAX_RESULTS):
    """Check one response. Returns a ValidationResult listing every rule broken."""
    output_ids = list(output_ids)
    catalog = set(catalog_ids)
    inputs = set(input_ids)
    problems = []

    unknown = [pid for pid in output_ids if pid not in catalog]
    if unknown:
        problems.append(f"unknown product ids: {unknown}")

    repeated = [pid for pid in output_ids if pid in inputs]
    if repeated:
        problems.append(f"returned ids from the request: {repeated}")

    if len(set(output_ids)) != len(output_ids):
        problems.append("duplicate ids")

    available = len(catalog - inputs)
    minimum = 1 if available > 0 else 0
    if not minimum <= len(output_ids) <= max_results:
        problems.append(
            f"expected {minimum} to {max_results} ids, got {len(output_ids)}"
        )

    return ValidationResult(valid=not problems, problems=problems)
