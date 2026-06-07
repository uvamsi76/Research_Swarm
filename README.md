# Research Swarm

Research Swarm is an end-to-end multi-agent research platform for company intelligence. Given a company name or query, the system runs specialist AI agents across founder, legal, financial, and market domains, gathers evidence from tools, validates results, and returns a structured report.

## Project Description

This project is a research swarm built around a centralized AI orchestrator and specialist agents. It is designed to answer complex company research requests such as founder info, legal status, financials, market dynamics, and corporate risk. The backend uses FastAPI and LangGraph to coordinate agents, while the frontend uses React and Server-Sent Events (SSE) to provide real-time progress.

## Architecture Overview

- `ui/`: React frontend with live dashboard and SSE progress updates.
- `apis/ai_swarm/`: FastAPI microservice that runs the LangGraph-based agent pipeline and generates PDF reports.
- `apis/tool_service/`: Separate FastAPI tool service exposing tool endpoints used by specialist agents.
- `custom-llm-deploy/`: Custom deployment artifacts for running Gemma 4 via vllm on a multi-GPU instance.
- `.github/workflows/`: CI builds Docker images and CD deploys backend services to Azure VMs.

### Flow

1. User submits a query from the frontend.
2. AI Swarm orchestrator decomposes the query into sub-tasks.
3. Specialist agents run in parallel: web, domain, financial, legal.
4. Devil's advocate and validator agents critique and verify findings.
5. Final answer, confidence data, and a PDF report are produced.
6. Frontend receives progress events over SSE.

## AI Tools Used

- LangGraph for multi-agent orchestration.
- Microsoft AI Foundry with `DeepSeek-V3-0324` as a configured production-grade model.
- Custom Gemma 4 deployment via `custom-llm-deploy/docker-compose-dyn.yml` with vllm.
- FastAPI for backend service delivery.
- React + Vite for frontend UI.
- Server-Sent Events (SSE) for real-time progress streaming.

## Local Setup

### 1. Configure environment

Copy the environment template and update your credentials:

```bash
cp .env.example .env
```

Edit `.env` and set:

- `LLM_PROVIDER` (openai, gemini, aifoundry)
- `LLM_MODEL` (`gpt-4`, `gemma-4-e2b-it`, `DeepSeek-V3-0324`, etc.)
- `LLM_API_KEY`
- `LLM_BASE_URL` when using Azure AI Foundry or custom endpoints
- `TOOL_SERVICE_URL` for the tool service endpoint

### 2. Backend services

Build and run the AI swarm backend:

```bash
docker build -t researchswarm-ai_swarm:local ./apis/ai_swarm
docker run -d --name researchswarm-ai_swarm -p 8000:8000 \
  -e LLM_PROVIDER=openai \
  -e LLM_MODEL=gpt-4 \
  -e LLM_API_KEY=your_api_key \
  -e TOOL_SERVICE_URL=http://localhost:3000 \
  researchswarm-ai_swarm:local
```

Build and run the tool service:

```bash
docker build -t researchswarm-tool_service:local ./apis/tool_service
docker run -d --name researchswarm-tool_service -p 3000:3000 researchswarm-tool_service:local
```

### 3. Frontend

Install and start the UI:

```bash
cd ui
npm install
npm run dev
```

Then open the app in the browser at `http://localhost:5173`.

### 4. Optional custom LLM deployment

If you want local Gemma 4 support, use the `custom-llm-deploy/` setup. It includes a `docker-compose-dyn.yml` and `nginx.sh` to route requests to vllm workers.

## Dependencies

### Backend

Key backend dependencies are listed in `apis/ai_swarm/requirements.txt` and include:

- `fastapi`
- `uvicorn`
- `langgraph`
- `langchain`
- `langchain-google-genai`
- `langchain-openai`
- `langsmith`
- `google-genai`
- `requests`
- `python-dotenv`
- `fpdf`

### Frontend

Frontend dependencies are in `ui/package.json`:

- `react`
- `react-dom`
- `vite`
- `typescript`
- `@vitejs/plugin-react`
- `concurrently`

## Deployment

### CI

The GitHub Actions workflow at `.github/workflows/ci.yml` builds and pushes Docker images for:

- `researchswarm-ai_swarm`
- `researchswarm-tool_service`

### CD

The workflow at `.github/workflows/cd.yml` deploys the backend services to Azure VMs using SSH and Docker:

- pulls the latest Docker images
- stops and removes existing containers
- starts `researchswarm-ai_swarm` on port `80` mapped to backend port `8000`
- starts `researchswarm-tool_service` on port `3000`

The project is deployed as follows:

- Frontend: https://research-swarm-rosy.vercel.app/
- Tool service backend: http://swarm-toolservice-api.duckdns.org
- API swarm backend: http://swarmapi.duckdns.org

Required GitHub secrets include:

- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`
- `AZURE_VM_AI_SWARM_HOST`
- `AZURE_VM_TOOL_SERVICE_HOST`
- `AZURE_VM_USERNAME`
- `AZURE_VM_SSH_KEY`
- `LLM_BASE_URL`
- `LLM_API_KEY`
- `LLM_PROVIDER`
- `LLM_MODEL`

## API Endpoints

### AI Swarm

- `GET /health`
- `POST /api/query` - synchronous query
- `POST /api/query/stream` - SSE query streaming
- `GET /api/report?query=...` - download generated PDF report

### Tool Service

- `GET /health`
- `GET /tools`
- `POST /tool/{tool_name}`

## Team

- **Vamsi** — end-to-end project and integration

