# recommendation v2: the agent version

A drop-in replacement for `src/recommendationservice` (v1). Same gRPC contract
(`ListRecommendations` in `protos/demo.proto`); the difference is who decides
which products to return.

**Status (week 7): skeleton.** The decision-maker is `PlaceholderAgent`, a
stand-in with the same interface the Gemini agent will have. Everything around
it is real and tested: server, deadline, validator, fallback, JSON logging,
health check, Docker image.

| File | Role |
|---|---|
| `server.py` | gRPC server: catalog → agent (with deadline) → validator → fallback → log |
| `agent.py` | `PlaceholderAgent` now, `GeminiAgent` in week 8; fault injection |
| `validator.py` | The correctness rules from the canary criteria table |
| `fallback.py` | v1's random logic, used when the agent fails |
| `catalog.py` | Product catalog client with timeouts |
| `jsonlog.py` | One JSON object per log line |
| `demo_client.py` | Calls v1 or v2 and prints the answer with product names |
| `tests/` | Unit tests and an end-to-end gRPC test with a fake catalog |

## Run locally next to v1

Assumes the `boutique` network and the `productcatalogservice` container from
Test 1 are running. Run from the repository root.

```bash
# Build (your machine's chip)
docker build --build-context protos=protos -t recommendationservice:v2 coen424/recommendation-v2

# Run the tests inside the image
docker run --rm --entrypoint python recommendationservice:v2 -m unittest discover -s tests

# Start v2 on port 8081 (v1 already uses 8080)
docker run -d --name recommendation-v2 --network boutique -p 8081:8080 \
  -e PRODUCT_CATALOG_SERVICE_ADDR=productcatalogservice:3550 \
  recommendationservice:v2

# See the catalog, then compare v1 and v2 on the same request
docker exec recommendation-v2 python demo_client.py --list
docker exec recommendation-v2 python demo_client.py --target recommendation-v1:8080 6E92ZMYYFZ
docker exec recommendation-v2 python demo_client.py --target localhost:8080 6E92ZMYYFZ
```

## Configuration (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `PRODUCT_CATALOG_SERVICE_ADDR` | required | Catalog address, e.g. `productcatalogservice:3550` |
| `PORT` | `8080` | Port v2 listens on inside the container |
| `AGENT_TIMEOUT_SECONDS` | `3` | Deadline for the agent; after it, fall back |
| `FALLBACK_ENABLED` | `true` | `false` = return a gRPC error instead of falling back |
| `FAULT_MODE` | `none` | `invalid_ids`, `slow` or `error`: inject a failure on purpose |
| `SERVICE_VERSION` | `v2` | Written into every log line |

## Every request logs one line

```json
{"event": "list_recommendations", "version": "v2", "source": "agent",
 "valid": true, "latency_ms": 12.4, "input_ids": ["6E92ZMYYFZ"],
 "output_ids": ["9SIQT8TOJO", "..."], "tool_calls": ["list_products"],
 "input_tokens": 0, "output_tokens": 0}
```

`valid` is true only when the agent's own answer was used. A fallback or an
error counts as a failure for the canary's correctness metric.

## Building for GKE

GKE nodes are amd64. On an Apple Silicon Mac, build for that chip explicitly:

```bash
docker build --platform linux/amd64 --build-context protos=protos \
  -t recommendationservice:v2-amd64 coen424/recommendation-v2
```
