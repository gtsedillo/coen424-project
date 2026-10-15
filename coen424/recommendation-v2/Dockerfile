# recommendation v2 (agent version)
#
# Build from the REPOSITORY ROOT. The gRPC contract is not copied into this
# folder: it is read from the shared protos/ folder, so v1 and v2 can never drift.
#
#   docker build --build-context protos=protos \
#       -t recommendationservice:v2 coen424/recommendation-v2
#
# Chip architecture is never hard-coded (unlike v1's Dockerfile):
#   - no --platform  -> your machine's chip (arm64 on Apple Silicon): local testing
#   - --platform linux/amd64 -> GKE nodes
#
# Python "slim" (Debian) instead of Alpine: grpcio ships ready-made wheels for
# both chips, so nothing has to be compiled.

# ---- Stage 1: install dependencies and generate gRPC code from the proto ----
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build
COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt \
 && pip install grpcio-tools==1.76.0

# "protos" is a named build context: the repository's protos/ folder.
COPY --from=protos demo.proto protos/demo.proto
RUN mkdir gen \
 && python -m grpc_tools.protoc -I protos \
        --python_out=gen --grpc_python_out=gen protos/demo.proto

# ---- Stage 2: the small runtime image ----
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app
COPY --from=builder /install /usr/local
COPY --from=builder /build/gen/ ./
COPY *.py ./
COPY tests/ tests/

# Run as a non-root user, as the Kubernetes manifests require (runAsNonRoot).
USER 1000:1000

EXPOSE 8080
ENTRYPOINT ["python", "server.py"]
