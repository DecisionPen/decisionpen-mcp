# DecisionPen MCP — Context Engine (research) + optional Edge sync (ingestion).
# Build from this repository root:
#   docker build -t decisionpen-mcp .
FROM python:3.12-slim

WORKDIR /app

RUN useradd --create-home --uid 10001 edge \
    && mkdir -p /data \
    && chown edge:edge /data

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY pyproject.toml README.md /app/
COPY decisionpen_mcp /app/decisionpen_mcp
RUN pip install --no-cache-dir -e . --no-deps

ENV PYTHONUNBUFFERED=1 \
    DP_SYNC_STATE_PATH=/data/sync_state.json \
    DP_MCP_AUDIT_LOG=/data/audit.jsonl \
    DP_MCP_MODE=cite_only

USER edge
VOLUME ["/data"]

ENTRYPOINT ["python", "-m", "decisionpen_mcp"]
CMD ["mcp"]
