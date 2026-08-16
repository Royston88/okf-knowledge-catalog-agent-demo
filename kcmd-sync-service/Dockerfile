# --- Build Stage ---
FROM node:22-slim AS builder

WORKDIR /app

# Copy library source and config files needed for compilation
COPY kcmd/package.json ./kcmd/
COPY kcmd/package-lock.json ./kcmd/
COPY kcmd/tsconfig.json ./kcmd/
COPY kcmd/tsconfig.tool.json ./kcmd/
COPY kcmd/src ./kcmd/

# Install all dependencies (including devDependencies like typescript)
WORKDIR /app/kcmd
RUN npm ci

# Compile TypeScript
RUN npm run build:libts
RUN npm run build:mcp

# --- Production Stage ---
FROM node:22-slim

WORKDIR /app

# Copy compiled library and its package.json
COPY --from=builder /app/kcmd/package.json ./kcmd/
COPY --from=builder /app/kcmd/build ./kcmd/build/

# Copy service files
COPY kcmd-sync-service/package.json kcmd-sync-service/package-lock.json* ./kcmd-sync-service/
COPY kcmd-sync-service/index.js ./kcmd-sync-service/

WORKDIR /app/kcmd-sync-service

# Install production dependencies.
# Since kcmd is a local file dependency ("file:../kcmd"),
# npm will link it and also install its dependencies.
RUN npm install --production

EXPOSE 8080
CMD ["npm", "start"]

