#!/bin/bash

# DC Validation Status - Build and Run Script
# Automatically starts Docker Desktop if needed and builds/runs the container

set -e  # Exit on any error

echo "🚀 Starting DC Validation Status setup..."

# Check if Docker Desktop is already running
if docker info >/dev/null 2>&1; then
    echo "✅ Docker is already running"
else
    echo "🐳 Starting Docker Desktop..."
    open -a Docker
    
    echo "⏳ Waiting for Docker to be ready..."
    timeout=60  # 60 second timeout
    elapsed=0
    
    while ! docker info >/dev/null 2>&1; do
        if [ $elapsed -ge $timeout ]; then
            echo "❌ Docker Desktop failed to start within $timeout seconds"
            echo "Please start Docker Desktop manually and try again"
            exit 1
        fi
        echo "   Docker not ready yet, waiting... (${elapsed}s)"
        sleep 2
        elapsed=$((elapsed + 2))
    done
    
    echo "✅ Docker is ready!"
fi

# Stop and remove existing container if it exists
if docker ps -a | grep -q dcvs; then
    echo "🧹 Cleaning up existing container..."
    docker stop dcvs >/dev/null 2>&1 || true
    docker rm dcvs >/dev/null 2>&1 || true
fi

# Build the container
echo "🔨 Building container..."
docker build -t dc-validation-status .

if [ $? -ne 0 ]; then
    echo "❌ Container build failed"
    exit 1
fi

echo "✅ Container built successfully"

# Run the container
echo "🚀 Starting container..."
docker run -d --name dcvs -p 8000:8000 -v "$HOME/.kube:/root/.kube:ro" -e KUBECONFIG=/root/.kube/config --restart unless-stopped dc-validation-status

if [ $? -eq 0 ]; then
    echo "✅ Container started successfully!"
    echo ""
    echo "🌐 Web interface available at: http://localhost:8000"
    echo "📊 API documentation at: http://localhost:8000/docs"
    echo ""
    echo "To view logs: docker logs dcvs"
    echo "To stop: docker stop dcvs"
    echo "To restart: docker start dcvs"
    echo ""
    echo "🚀 Opening web interface in your default browser..."
    open http://localhost:8000
else
    echo "❌ Failed to start container"
    exit 1
fi