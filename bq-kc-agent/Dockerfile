# --- Build Node.js parts (kcmd) ---
FROM node:22-slim AS node-builder
WORKDIR /app
COPY kcmd/package.json ./kcmd/
COPY kcmd/package-lock.json ./kcmd/
COPY kcmd/tsconfig.json ./kcmd/
COPY kcmd/tsconfig.tool.json ./kcmd/
COPY kcmd/src ./kcmd/
WORKDIR /app/kcmd
RUN npm ci
RUN npm run build:libts
RUN npm run build:mcp
RUN npm prune --production

# --- Build Python parts and final image ---
FROM python:3.12-slim

# Install Node.js (needed to run the MCP server)
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv==0.8.13

WORKDIR /code

# Copy built kcmd from node-builder
COPY --from=node-builder /app/kcmd ./kcmd

# Copy python agent code
COPY bq-kc-agent/pyproject.toml bq-kc-agent/README.md bq-kc-agent/uv.lock* ./
COPY bq-kc-agent/app ./app

# Sync python dependencies
RUN uv sync --frozen

# Copy the workspace skeleton
COPY bq-okf-workspace ./bq-okf-workspace

ARG AGENT_VERSION=0.0.0
ENV AGENT_VERSION=${AGENT_VERSION}

# Set environment variables for the agent to find kcmd
ENV KCMD_PATH=/code/kcmd
ENV KCMD_WORKSPACE=/code/bq-okf-workspace

EXPOSE 8080

CMD ["uv", "run", "uvicorn", "app.fast_api_app:app", "--host", "0.0.0.0", "--port", "8080"]

