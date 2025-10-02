#!/bin/bash

# Deployment script for Web Crawler API and MCP Server to Google Cloud Run
# 
# Usage:
#   ./deploy.sh PROJECT_ID [REGION]
#
# Example:
#   ./deploy.sh my-gcp-project us-central1

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if PROJECT_ID is provided
if [ -z "$1" ]; then
    echo -e "${RED}Error: PROJECT_ID is required${NC}"
    echo "Usage: $0 PROJECT_ID [REGION]"
    exit 1
fi

PROJECT_ID=$1
REGION=${2:-us-central1}

echo -e "${GREEN}Starting deployment to Google Cloud Run${NC}"
echo "Project ID: $PROJECT_ID"
echo "Region: $REGION"
echo ""

# Set the project
echo -e "${YELLOW}Setting GCP project...${NC}"
gcloud config set project $PROJECT_ID

# Enable required APIs
echo -e "${YELLOW}Enabling required APIs...${NC}"
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com

# Build and deploy Crawler API
echo ""
echo -e "${GREEN}=== Deploying Crawler API ===${NC}"
echo -e "${YELLOW}Building container image...${NC}"

# Create temporary cloudbuild config for API
cat > /tmp/crawler-api-build.yaml <<'EOFBUILD'
steps:
- name: 'gcr.io/cloud-builders/docker'
  args: ['build', '-f', 'api/Dockerfile', '-t', 'gcr.io/$PROJECT_ID/crawler-api', '.']
images: ['gcr.io/$PROJECT_ID/crawler-api']
EOFBUILD

gcloud builds submit --config /tmp/crawler-api-build.yaml .

echo -e "${YELLOW}Deploying to Cloud Run...${NC}"
gcloud run deploy crawler-api \
    --image gcr.io/$PROJECT_ID/crawler-api \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --memory 1Gi \
    --timeout 300 \
    --max-instances 10 \
    --set-env-vars "LOG_LEVEL=INFO"

# Get the Crawler API URL
CRAWLER_API_URL=$(gcloud run services describe crawler-api \
    --platform managed \
    --region $REGION \
    --format 'value(status.url)')

echo -e "${GREEN}Crawler API deployed at: $CRAWLER_API_URL${NC}"

# Build and deploy MCP Server
echo ""
echo -e "${GREEN}=== Deploying MCP Server ===${NC}"
echo -e "${YELLOW}Building container image...${NC}"

# Create temporary cloudbuild config for MCP
cat > /tmp/mcp-server-build.yaml <<'EOFBUILD'
steps:
- name: 'gcr.io/cloud-builders/docker'
  args: ['build', '-t', 'gcr.io/$PROJECT_ID/mcp-server', '.']
images: ['gcr.io/$PROJECT_ID/mcp-server']
EOFBUILD

gcloud builds submit --config /tmp/mcp-server-build.yaml mcp-server/

echo -e "${YELLOW}Deploying to Cloud Run...${NC}"
gcloud run deploy mcp-server \
    --image gcr.io/$PROJECT_ID/mcp-server \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --memory 512Mi \
    --timeout 300 \
    --max-instances 10 \
    --set-env-vars "CRAWLER_API_URL=$CRAWLER_API_URL"

# Get the MCP Server URL
MCP_SERVER_URL=$(gcloud run services describe mcp-server \
    --platform managed \
    --region $REGION \
    --format 'value(status.url)')

echo -e "${GREEN}MCP Server deployed at: $MCP_SERVER_URL${NC}"

# Summary
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Crawler API URL: $CRAWLER_API_URL"
echo "MCP Server URL: $MCP_SERVER_URL"
echo ""
echo "Test the API:"
echo "  curl $CRAWLER_API_URL/health"
echo ""
echo "API Documentation:"
echo "  $CRAWLER_API_URL/"
echo ""
echo "Configure Cursor MCP client with:"
echo "  Server URL: $MCP_SERVER_URL"
echo ""

