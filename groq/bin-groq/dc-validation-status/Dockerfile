# ---- 1) Build the frontend (Vite) ----
FROM node:20 AS build-web
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build      # outputs /app/dist

# ---- 2) Python runtime with Uvicorn ----
FROM python:3.11-slim
WORKDIR /app

# System deps (including ipmitool for BMC authentication testing)
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    ca-certificates \
    tzdata \
    ipmitool \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

# ---- install kubectl (matches container OS/arch) ----
ARG KUBECTL_VERSION=v1.30.3
ARG TARGETOS=linux
ARG TARGETARCH=amd64
RUN apt-get update -y && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/* \
 && curl -fsSLo /usr/local/bin/kubectl "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/${TARGETOS}/${TARGETARCH}/kubectl" \
 && chmod +x /usr/local/bin/kubectl \
 && kubectl version --client


# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY server.py utils.py bmctools.py ./
COPY requirements/ ./requirements/
# Bring in the built frontend
COPY --from=build-web /app/dist ./dist

# Expose API/HTTP port
EXPOSE 8000


# Run the server (single-process; simplest)
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]

