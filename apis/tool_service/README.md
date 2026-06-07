# Tool Service

Microservice providing a registry of tools for the AI Swarm Service. Handles tool invocation, error handling, and response formatting.

## Overview

The Tool Service is a FastAPI-based microservice that:
- Registers and exposes tools available to AI agents
- Handles remote tool execution with error handling
- Provides a simple REST API for tool discovery and invocation
- Returns standardized responses for all tool calls

## Available Tools

- `web_search` - Search the web for information
- `scrape_url` - Extract content from a URL
- `knowledge_base_lookup` - Query internal knowledge base
- `get_expert_report` - Retrieve expert analysis on a topic
- `get_market_data` - Fetch market data for a ticker
- `get_earnings_report` - Get company earnings reports
- `financial_model` - Run financial calculations
- `search_case_law` - Search legal case law
- `lookup_statute` - Look up statute information
- `compliance_check` - Perform compliance analysis

## Getting Started

### Requirements

- Python 3.11+
- pip dependencies (see requirements.txt)

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the service
python -m tool_service

# Service will be available at http://localhost:3000
```

### Docker

```bash
# Build the image
docker build -t tool_service:latest .

# Run the container
docker run -p 3000:3000 tool_service:latest
```

## API Endpoints

### Health Check
```bash
GET /health
```

Response:
```json
{
  "status": "ok",
  "service": "LangGraph Tool Service"
}
```

### List Available Tools
```bash
GET /tools
```

Response:
```json
{
  "tools": [
    "compliance_check",
    "financial_model",
    "get_earnings_report",
    "get_expert_report",
    "get_market_data",
    "knowledge_base_lookup",
    "lookup_statute",
    "scrape_url",
    "search_case_law",
    "web_search"
  ]
}
```

### Invoke a Tool
```bash
POST /tool/{tool_name}
Content-Type: application/json

{
  "args": [],
  "kwargs": {
    "query": "example search query"
  }
}
```

Response:
```json
{
  "output": "[TOOL_NAME] Results..."
}
```

## Tool Invocation Examples

### Web Search
```bash
curl -X POST http://localhost:3000/tool/web_search \
  -H "Content-Type: application/json" \
  -d '{"args": ["AI market trends 2025"], "kwargs": {}}'
```

### Scrape URL
```bash
curl -X POST http://localhost:3000/tool/scrape_url \
  -H "Content-Type: application/json" \
  -d '{"args": ["https://example.com"], "kwargs": {}}'
```

### Market Data
```bash
curl -X POST http://localhost:3000/tool/get_market_data \
  -H "Content-Type: application/json" \
  -d '{"args": [], "kwargs": {"ticker": "AAPL"}}'
```

## Error Handling

Tools return error messages in the `output` field with format:
```
[TOOL ERROR — {tool_name}] {error_type}: {error_message}
```

If a tool is not found, the API returns HTTP 404:
```json
{
  "detail": "Tool 'nonexistent_tool' is not available."
}
```

If arguments are invalid, the API returns HTTP 400:
```json
{
  "detail": "Invalid arguments for tool {tool_name}"
}
```

## Architecture

```
HTTP Request
    ↓
Tool Lookup
    ↓
Argument Validation
    ↓
Tool Execution
    ↓
Error Handling
    ↓
Response Formatting
```

## Integration with AI Swarm

The AI Swarm Service calls this service via HTTP POST for each tool invocation:

1. AI agent decides to call a tool
2. AI Swarm makes HTTP POST to `/tool/{tool_name}`
3. Tool Service executes the tool
4. Response returned with results or error
5. AI Swarm processes the response

## Extending Tools

To add a new tool:

1. Add function to `impl.py`:
```python
def new_tool(param: str) -> str:
    try:
        # Tool implementation
        return f"[NEW_TOOL] Result..."
    except Exception as exc:
        return _tool_error("new_tool", exc)
```

2. Register in `TOOL_REGISTRY`:
```python
TOOL_REGISTRY: Dict[str, Callable[..., str]] = {
    ...
    "new_tool": new_tool,
}
```

## Performance Notes

- All tools are stateless and can run in parallel
- Implement timeouts in tool implementations as needed
- Tool Service can be horizontally scaled

## Docker Compose Integration

Run with AI Swarm:
```yaml
services:
  tool_service:
    build: ./tool_service
    ports:
      - "3000:3000"
    environment:
      - LOG_LEVEL=info

  ai_swarm:
    build: ./ai_swarm
    ports:
      - "8000:8000"
    environment:
      - TOOL_SERVICE_URL=http://tool_service:3000
      - LLM_PROVIDER=openai
      - LLM_API_KEY=${LLM_API_KEY}
    depends_on:
      - tool_service
```

## Troubleshooting

**Tool not found**
- List available tools with `GET /tools`
- Verify tool name is registered in `impl.py`

**Invalid arguments**
- Check tool signature in implementation
- Ensure args and kwargs match tool parameters

**Service connection errors**
- Verify service is running and port is accessible
- Check firewall and network settings

## License

Part of Hackathon_Microsoft project
