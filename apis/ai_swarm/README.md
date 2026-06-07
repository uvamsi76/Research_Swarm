# AI Swarm Service

Multi-agent research orchestration service powered by LangGraph. Coordinates multiple specialist agents to research, critique, and validate complex queries across web, domain, financial, and legal domains.

## Overview

The AI Swarm Service is a FastAPI-based microservice that:
- Orchestrates multiple AI agents for specialized research tasks
- Coordinates parallel execution of web retrieval, domain expertise, financial analysis, and legal research
- Performs adversarial critique and validation of findings
- Generates comprehensive PDF reports with confidence scoring

## Services

- **Orchestrator**: Decomposes queries into task lists for specialist agents
- **Specialist Agents**: Web retriever, domain expert, financial analyst, legal analyst
- **Devil's Advocate**: Critiques findings and identifies gaps
- **Validator**: Synthesizes final answer with confidence levels

## Getting Started

### Requirements

- Python 3.11+
- pip dependencies (see requirements.txt)

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the service
python -m ai_swarm

# Service will be available at http://localhost:8000
```

### Docker

```bash
# Build the image
docker build -t ai_swarm:latest .

# Run the container
docker run -p 8000:8000 \
  -e LLM_PROVIDER=openai \
  -e LLM_MODEL=gpt-4 \
  -e LLM_API_KEY=your_api_key \
  -e TOOL_SERVICE_URL=http://tool_service:3000 \
  ai_swarm:latest
```

## API Endpoints

### Health Check
```bash
GET /health
```

### Query Stream (SSE)
```bash
POST /api/query/stream
Content-Type: application/json

{
  "query": "Your research question here"
}
```

Returns Server-Sent Events with real-time progress updates.

### Get Report
```bash
GET /api/report?query=your_query
```

Returns generated PDF report.

### Run Query (Synchronous)
```bash
POST /api/query
Content-Type: application/json

{
  "query": "Your research question here"
}
```

Returns JSON with final answer, validation, confidence, and agent statuses.

## Environment Variables

- `LLM_PROVIDER`: LLM provider (openai, gemini) - default: openai
- `LLM_MODEL`: Model identifier - default: gpt-4
- `LLM_TEMPERATURE`: Model temperature (0.0-1.0) - default: 1.0
- `LLM_API_KEY`: API key for the LLM provider
- `LLM_BASE_URL`: Optional custom base URL
- `LLM_MAX_RETRIES`: Max retries for LLM calls - default: 2
- `TOOL_SERVICE_URL`: URL for tool service - default: http://localhost:3000

## Architecture

```
Query Input
    ↓
Orchestrator (planning)
    ↓
Parallel Specialists:
├─ Web Retriever
├─ Domain Expert
├─ Financial Analyst
└─ Legal Analyst
    ↓
Devil's Advocate (critique)
    ↓
Validator (synthesis)
    ↓
PDF Report + JSON Response
```

## Logging

Logs are sent to stdout. Configure via environment or Python logging.

## Dependencies

Key dependencies:
- fastapi - Web framework
- langgraph - Agent orchestration
- langchain - LLM integration
- fpdf - PDF generation
- pydantic - Data validation

See requirements.txt for full list.

## Performance Notes

- Specialist agents run in parallel for efficiency
- SSE streaming provides real-time progress feedback
- PDF generation is cached for repeat queries
- Tool service calls are instrumented for monitoring

## Troubleshooting

**UnicodeEncodeError in PDF generation**
- Ensure the pdf_report.py has encoding="replace" for unsupported characters

**Tool service connection errors**
- Verify TOOL_SERVICE_URL is correct and accessible
- Check tool service logs for errors

**LLM API errors**
- Verify API keys and model names
- Check network connectivity to LLM provider

## License

Part of Hackathon_Microsoft project
