"""recommendation v2: same gRPC contract as v1, but an agent makes the decision.

Request flow (see the sequence diagram in the D3 deck):
  1. fetch the catalog (needed by the validator)
  2. ask the agent, with a deadline
  3. validate the agent's answer
  4. if the agent failed, timed out or answered wrongly: v1-style fallback
     (or a gRPC error when FALLBACK_ENABLED=false)
  5. log one JSON line with everything the canary needs

Configuration comes from environment variables, like v1:
  PORT                          default 8080
  PRODUCT_CATALOG_SERVICE_ADDR  required, e.g. productcatalogservice:3550
  AGENT_TIMEOUT_SECONDS         default 3
  FALLBACK_ENABLED              default true
  FAULT_MODE                    none | invalid_ids | slow | error (default none)
  SERVICE_VERSION               default v2 (written into every log line)
"""

import os
import time
import uuid
from concurrent import futures

import grpc
from grpc_health.v1 import health, health_pb2, health_pb2_grpc

import demo_pb2
import demo_pb2_grpc
from agent import PlaceholderAgent
from catalog import Catalog
from fallback import fallback_recommendations
from jsonlog import get_logger
from validator import validate

logger = get_logger("recommendationservice-v2")


class RecommendationServiceV2(demo_pb2_grpc.RecommendationServiceServicer):
    def __init__(self, catalog, agent, timeout_seconds=3.0, fallback_enabled=True,
                 version="v2"):
        self._catalog = catalog
        self._agent = agent
        self._timeout = timeout_seconds
        self._fallback_enabled = fallback_enabled
        self._version = version
        # Agent calls run here, so we can stop waiting after the deadline.
        self._agent_pool = futures.ThreadPoolExecutor(max_workers=10)

    def ListRecommendations(self, request, context):
        started = time.perf_counter()
        input_ids = list(request.product_ids)
        record = {
            "event": "list_recommendations",
            "version": self._version,
            "request_id": uuid.uuid4().hex,
            "user_id": request.user_id,
            "input_ids": input_ids,
            "agent": self._agent.name,
        }

        try:
            catalog_ids = [p.id for p in self._catalog.list_products()]
        except grpc.RpcError as exc:
            self._log(record, started, status="error", reason=f"catalog unavailable: {exc.code()}")
            context.abort(grpc.StatusCode.UNAVAILABLE, "product catalog unavailable")

        output_ids, reason, result = None, None, None
        pending = self._agent_pool.submit(
            self._agent.recommend, request.user_id, input_ids, self._catalog
        )
        try:
            result = pending.result(timeout=self._timeout)
            check = validate(result.product_ids, input_ids, catalog_ids)
            if check.valid:
                output_ids = list(result.product_ids)
            else:
                reason = "invalid answer: " + "; ".join(check.problems)
        except futures.TimeoutError:
            reason = f"agent timed out after {self._timeout}s"
        except Exception as exc:  # any agent failure must end in a fallback, never a crash
            reason = f"agent error: {exc}"

        if result is not None:
            record.update(
                model=result.model,
                tool_calls=result.tool_calls,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
            )

        if output_ids is None:
            if not self._fallback_enabled:
                self._log(record, started, status="error", reason=reason)
                context.abort(grpc.StatusCode.INTERNAL, reason)
            output_ids = fallback_recommendations(catalog_ids, input_ids)
            self._log(record, started, status="ok", source="fallback", reason=reason,
                      output_ids=output_ids)
        else:
            self._log(record, started, status="ok", source="agent", output_ids=output_ids)

        return demo_pb2.ListRecommendationsResponse(product_ids=output_ids)

    def _log(self, record, started, **fields):
        record.update(fields)
        record["latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
        # valid = the agent's own answer was used. Fallbacks and errors count as failures.
        record["valid"] = record.get("source") == "agent"
        logger.info("ListRecommendations", extra={"fields": record})


def env_flag(name, default):
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes")


def build_server(service, port):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    demo_pb2_grpc.add_RecommendationServiceServicer_to_server(service, server)

    # Standard gRPC health service, used by Kubernetes readiness/liveness probes.
    health_servicer = health.HealthServicer()
    health_servicer.set("", health_pb2.HealthCheckResponse.SERVING)
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)

    bound_port = server.add_insecure_port(f"[::]:{port}")
    return server, bound_port


def main():
    port = os.environ.get("PORT", "8080")
    catalog_addr = os.environ.get("PRODUCT_CATALOG_SERVICE_ADDR", "")
    if not catalog_addr:
        raise SystemExit("PRODUCT_CATALOG_SERVICE_ADDR environment variable not set")

    agent = PlaceholderAgent(fault_mode=os.environ.get("FAULT_MODE", "none"))
    service = RecommendationServiceV2(
        catalog=Catalog(grpc.insecure_channel(catalog_addr)),
        agent=agent,
        timeout_seconds=float(os.environ.get("AGENT_TIMEOUT_SECONDS", "3")),
        fallback_enabled=env_flag("FALLBACK_ENABLED", True),
        version=os.environ.get("SERVICE_VERSION", "v2"),
    )
    server, _ = build_server(service, port)
    server.start()
    logger.info(
        f"listening on port: {port}",
        extra={"fields": {
            "catalog_addr": catalog_addr,
            "agent": agent.name,
            "fault_mode": agent.fault_mode,
        }},
    )
    server.wait_for_termination()


if __name__ == "__main__":
    main()
