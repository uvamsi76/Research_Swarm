# ResearchSwarm: AI-Powered Company Profile Builder

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Multi--Agent-green)](https://github.com/langchain-ai/langgraph)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.136%2B-brightgreen)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Compose-blue)](https://www.docker.com/)

A sophisticated multi-agent research system that generates comprehensive company profiles by orchestrating specialized AI agents to collect, validate, and synthesize information across financial, founder, market, legal, and sentiment dimensions.

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Usage](#usage)
- [API Documentation](#api-documentation)
- [Configuration](#configuration)
- [Performance & Scaling](#performance--scaling)
- [Components Deep Dive](#components-deep-dive)

## Overview

ResearchSwarm is an enterprise-grade company profiling system that leverages multi-agent AI orchestration to deliver comprehensive, validated insights. When given a query about a company, the system:

1. **Decomposes** the query into specific research tasks
2. **Dispatches** parallel specialist agents for different domains
3. **Streams Real-time Progress** via Server-Sent Events (SSE) to the frontend dashboard
4. **Collects** and correlates findings across multiple sources
5. **Critiques** results for contradictions and gaps
6. **Validates** claims with source attribution
7. **Synthesizes** into a professional PDF report with confidence scoring

### Example Query
```
"What is the investment potential of TechCorp for Series B funding in the AI/ML sector?"
```

### Output Dimensions
- **Financial Profile**: Revenue, funding history, burn rate, cash runway, profitability metrics
- **Founder/Team**: Background, expertise, previous exits, leadership track record
- **Customer Sentiment**: NPS, user reviews, market perception, churn signals
- **Market Dynamics**: TAM, growth rates, market trends, industry direction
- **Competitive Position**: Direct competitors, market share, differentiation
- **Legal & IP**: Patents, litigation history, regulatory compliance, licensing

## Key Features

### Multi-Agent Orchestration
- **Orchestrator Agent**: Decomposes queries into 5-8 specific tasks per specialist
- **Specialist Agents** (4 in parallel):
  - Financial Analyst: Market data, earnings, financial models
  - Domain Expert: Internal knowledge base, expert reports
  - Web Researcher: Web search, content scraping, news monitoring
  - Legal Analyst: Case law, statutes, compliance, patents
- **Devil's Advocate**: Identifies contradictions, missing data, unsupported claims
- **Validator Agent**: Validates findings with source attribution, confidence scoring

### Intelligent Tool Management
- Decoupled tool service prevents blocking of LLM requests
- Handles long-running operations: web scraping, API calls, data aggregation
- Graceful error handling with partial result support

### Flexible LLM Support
- **Open-source**: Gemma-4 (deployed on Jarvis Labs)
- **Closed-source**: Azure AI Foundry, OpenAI
- Environment-configurable provider selection
- Fallback mechanisms and retry policies

### Real-time Progress Streaming with Server-Sent Events (SSE)
- **Bidirectional Communication**: Frontend subscribes to live event stream from backend
- **Server-Sent Events (SSE)**: Persistent HTTP connection pushes real-time updates without polling
- **Agent Status Tracking**: Per-node progress indicators (orchestrator, specialists, critics, validators)
- **Tool Execution Monitoring**: Real-time feedback on tool calls, successes, and failures
- **Live Metrics**: Sources found, claims verified, conflicts detected, processing pipeline stage
- **Event Types**: Agent status, progress updates, tool execution, findings, metrics, confidence scoring, report generation, completion

### Enterprise Reporting
- Auto-generated PDF reports with styling and formatting
- Executive summary with confidence scoring
- Full research trail with source attribution
- Data gap identification and impact analysis

## System Architecture

### High-Level Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React)                         │
│                    http://localhost:5173                         │
└────────────────────────────┬──────────────────────────────────────┘
                             │ query
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  AI_SWARM SERVICE (Port 8000)                   │
│                  ┌─────────────────────────┐                    │
│                  │   LANGGRAPH Pipeline    │                    │
│    ┌─────────────────────────────────────────────────────┐     │
│    │                                                     │      │
│    │  ┌──────────────┐      ┌──────────────────────┐    │      │
│    │  │ Orchestrator │──┬──▶│  Specialist Agents   │    │      │
│    │  │  (5-8 tasks) │  │   │  (Parallel Exec)     │    │      │
│    │  └──────────────┘  │   │  ┌────────────────┐  │    │      │
│    │                    │   │  │ Financial      │  │    │      │
│    │                    │   │  │ Domain Expert  │  │    │      │
│    │                    │   │  │ Web Researcher │  │    │      │
│    │                    │   │  │ Legal Analyst  │  │    │      │
│    │                    │   │  └────────────────┘  │    │      │
│    │                    │   └──────────────────────┘    │      │
│    │                    │            │                  │      │
│    │                    └────────────┬───────────────────│──────┼──────┐
│    │                                 ▼                  │      │      │
│    │                    ┌──────────────────────┐        │      │   (if tool call)
│    │                    │   Devil's Advocate   │        │      │      │
│    │                    │  (Critique & Gap     │        │      │      │
│    │                    │   Analysis)          │        │      │      │
│    │                    └──────────────────────┘        │      │      │
│    │                             │                       │      │      │
│    │                             ▼                       │      │      │
│    │                    ┌──────────────────────┐        │      │      │
│    │                    │   Validator Agent    │        │      │      │
│    │                    │  (Claims Validation  │        │      │      │
│    │                    │   & Source Find)     │        │      │      │
│    │                    └──────────────────────┘        │      │      │
│    │                             │                       │      │      │
│    │                             ▼                       │      │      │
│    │                    ┌──────────────────────┐        │      │      │
│    │                    │  PDF Report Builder  │        │      │      │
│    │                    └──────────────────────┘        │      │      │
│    │                                                     │      │      │
│    └─────────────────────────────────────────────────────┘      │      │
│                                                                  │      │
│  ┌─────────────────────────────────────────────────────────────┐│      │
│  │              LLM INTEGRATION LAYER                         ││      │
│  │  ┌────────────────────┐        ┌────────────────────┐    ││      │
│  │  │  Gemma-4           │        │  Azure AI Foundry  │    ││      │
│  │  │  (Jarvis Labs)     │        │  (Closed-source)   │    ││      │
│  │  │  OPEN SOURCE        │        │  + OpenAI/Gemini   │    ││      │
│  │  └────────────────────┘        └────────────────────┘    ││      │
│  │                                                            ││      │
│  └────────────────────────────────────────────────────────────┘│      │
│                                                                 │      │
│  SSE Streaming ◀─────────────────────────────────────────────┘│      │
│  (Real-time progress updates via persistent HTTP connection)   │      │
└──────────────────────────────────────────────────────────────────┘      │
                                                                           │
                                                        (Tool Requests)    │
                                                                           ▼
┌───────────────────────────────────────────────────────────────────────┐
│              TOOL SERVICE (Port 3000)                                  │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────┐   │
│  │            TOOL REGISTRY & EXECUTOR                           │   │
│  │                                                               │   │
│  │  ┌──────────────────┐  ┌──────────────────┐                 │   │
│  │  │  Web Tools       │  │  Data Tools      │                 │   │
│  │  │ - web_search    │  │ - scrape_url    │                 │   │
│  │  │ - scrape_url    │  │ - get_market_data│                 │   │
│  │  └──────────────────┘  └──────────────────┘                 │   │
│  │                                                               │   │
│  │  ┌──────────────────┐  ┌──────────────────┐                 │   │
│  │  │  Finance Tools   │  │  Legal Tools     │                 │   │
│  │  │ - get_market_data│  │ - search_case_law│                 │   │
│  │  │ - get_earnings   │  │ - lookup_statute │                 │   │
│  │  │ - financial_model│  │ - compliance_check│                 │   │
│  │  └──────────────────┘  └──────────────────┘                 │   │
│  │                                                               │   │
│  │  ┌──────────────────┐                                        │   │
│  │  │  Knowledge Tools │                                        │   │
│  │  │ - kb_lookup      │                                        │   │
│  │  │ - get_expert_report│                                      │   │
│  │  └──────────────────┘                                        │   │
│  │                                                               │   │
│  └───────────────────────────────────────────────────────────────┘   │
│                                                                         │
└───────────────────────────────────────────────────────────────────────┘
        ▲                                                      ▲
        └──────────────────────────────────────────────────────┘
              (Tool Results w/ Full Context)
```

### Data Flow Sequence

```
1. Frontend sends query
   │
2. Orchestrator breaks down query
   ├─ Task List: ["Get Q3 revenue", "Find founders", "Check patents", ...]
   │
3. Specialist Agents Execute (Parallel)
   ├─ Agent → LLM ("I need to do: [task]")
   ├─ LLM → Response with Tool Calls
   ├─ Agent → Tool Service ("/tool/web_search")
   ├─ Tool Service → Execute & Return Results
   ├─ Agent → LLM with Results ("Here's what I found: [results]")
   ├─ LLM → Final Analysis
   └─ Agent → Return to Pipeline
   
4. All Results Collected
   │
5. Devil's Advocate Analysis
   ├─ Identifies contradictions
   ├─ Flags missing data
   └─ Produces critique
   
6. Validator
   ├─ Validates each claim
   ├─ Finds sources
   ├─ Sets confidence levels
   └─ Produces final answer
   
7. Report Generation
   ├─ Synthesizes all findings
   ├─ Formats PDF
   └─ Returns with confidence score
```

### Server-Sent Events (SSE) Implementation

The backend implements **Server-Sent Events** to push real-time progress updates to the frontend without polling. This enables live dashboards that update instantly as agents execute.

#### How SSE Works in ResearchSwarm

```
Frontend                          Backend (AI Swarm)
   │                                   │
   ├──── GET /api/query/stream ────────▶
   │      (opens persistent HTTP connection)
   │                                   │
   │◀──── event: status ────────────────┤
   │      data: {"status": "started"}   │
   │                                   │
   │◀──── event: agent ─────────────────┤ (Orchestrator starts)
   │      data: {"id": "orchestrator"...│
   │                                   │
   │◀──── event: progress ──────────────┤ (LLM requested)
   │      data: {"progress": 10...}     │
   │                                   │
   │◀──── event: agent ─────────────────┤ (Specialists start)
   │      data: {"id": "financial"...   │
   │                                   │
   │◀──── event: tool ──────────────────┤ (Tool called)
   │      data: {"tool_name": "web...   │
   │                                   │
   │◀──── event: agent ─────────────────┤ (Results processed)
   │      data: {"progress": 50...}     │
   │                                   │
   │      ... (parallel execution) ...  │
   │                                   │
   │◀──── event: agent ─────────────────┤ (Devil's Advocate)
   │      data: {"id": "devil"...       │
   │                                   │
   │◀──── event: agent ─────────────────┤ (Validator runs)
   │      data: {"id": "validator"...   │
   │                                   │
   │◀──── event: report ────────────────┤ (PDF generation)
   │      data: {"status": "ready"...   │
   │                                   │
   │◀──── event: complete ──────────────┤ (All done)
   │      data: {"query": "...", "is_   │
   │             valid": true...}       │
   │                                   │
```

#### Event Types & Data Structure

| Event Type | Triggered When | Example Data |
|-----------|---|---|
| `status` | Pipeline starts/completes | `{"status": "started\|done"}` |
| `agent` | Agent state changes | `{"id": "financial", "state": "active\|done", "progress": 50}` |
| `progress` | Node progress updates | `{"node": "web_agent", "progress": 65, "detail": "tool executed: web_search"}` |
| `tool` | Tool executes (success/failure) | `{"tool_name": "web_search", "status": "success\|failure"}` |
| `finding` | Discovery made | `{"tag": "company_info", "text": "Founded in 2020..."}` |
| `metric` | Metrics update | `{"id": "sources", "value": 15}` |
| `topic` | Topic coverage changes | `{"index": 0, "value": 75}` |
| `confidence` | Confidence changes | `{"value": 68}` |
| `report` | PDF generation updates | `{"status": "started\|ready"}` |
| `error` | Error occurs | `{"message": "Tool service timeout"}` |
| `complete` | Pipeline finishes | `{"query": "...", "is_valid": true, "confidence": "high"...}` |

#### Backend Implementation Files

- **`apis/ai_swarm/progress.py`**: Tracks agent/node progress with SSE emission
- **`apis/ai_swarm/sse.py`**: Event formatting and queuing for SSE responses
- **`apis/ai_swarm/app.py`**: FastAPI endpoint `/api/query/stream` handling SSE

#### Frontend Integration

The React frontend connects via `EventSource` API:

```javascript
// Open persistent SSE connection
const source = new EventSource(`/api/query/stream?query=${encodeURIComponent(query)}`);

// Listen to all event types
source.addEventListener('agent', (event) => {
  const data = JSON.parse(event.data);
  updateAgent(data);  // Update UI with agent status
});

source.addEventListener('progress', (event) => {
  const data = JSON.parse(event.data);
  updateProgress(data);  // Update progress bars
});

source.addEventListener('complete', (event) => {
  source.close();  // Close connection when done
  showResults();   // Display final results
});
```

#### Advantages of SSE for ResearchSwarm

1. **No Polling Overhead**: Single persistent connection vs. repeated HTTP requests
2. **Low Latency**: Immediate updates as agents execute
3. **Built-in Reconnection**: Automatic reconnection if connection drops
4. **Efficient**: Single HTTP connection for all events
5. **Browser Native**: No WebSocket complexity, works with standard HTTP
6. **Real-time Dashboard**: Dashboard updates live without user refresh
7. **Tool Monitoring**: See each tool execution in real-time
8. **Error Visibility**: Immediate notification of failures
9. **Progress Transparency**: Clear visibility into multi-agent parallel execution

#### Scaling Considerations for SSE

- Each SSE connection holds a server resource (thread/async task)
- For N concurrent users, server maintains N open connections
- Minimal memory overhead (~1KB per connection)
- Connection pooling optimizes resource usage
- Timeout mechanisms (30s default) clean up stale connections

## Project Structure

```
Hackathon_Microsoft/
├── apis/
│   ├── ai_swarm/                    # Main orchestration service
│   │   ├── __main__.py
│   │   ├── app.py                   # FastAPI server
│   │   ├── pipeline.py              # LangGraph pipeline definition
│   │   ├── agents.py                # Agent implementations
│   │   ├── llm.py                   # LLM provider abstraction
│   │   ├── tools.py                 # Tool definitions
│   │   ├── models.py                # Data models
│   │   ├── progress.py              # Progress tracking & SSE
│   │   ├── sse.py                   # SSE event formatting
│   │   ├── pdf_report.py            # PDF generation
│   │   ├── config.py                # Configuration
│   │   ├── Dockerfile               # Container definition
│   │   ├── README.md
│   │   └── requirements.txt
│   │
│   └── tool_service/                # Decoupled tool execution
│       ├── __main__.py
│       ├── app.py                   # FastAPI server
│       ├── impl.py                  # Tool implementations
│       ├── models.py                # Data models
│       ├── Dockerfile
│       ├── README.md
│       └── requirements.txt
│
├── ui/                              # React frontend
│   ├── src/
│   │   ├── App.tsx
│   │   ├── Dashboard.tsx            # Live research dashboard
│   │   ├── Home.tsx                 # Landing page
│   │   ├── types.ts
│   │   └── index.css
│   ├── package.json
│   ├── vite.config.ts
│   └── tsconfig.json
│
├── docker-compose.yml               # Service orchestration
├── .env.example                     # Configuration template
└── DOCKER_SETUP.md                  # Deployment guide
```

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+ (for frontend)
- Docker & Docker Compose (optional)
- API keys for LLM providers (OpenAI, Gemini, or Azure AI Foundry)

### Local Development Setup

#### 1. Backend Setup

```bash
# Navigate to project root
cd /path/to/Hackathon_Microsoft

# Create Python virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
cd apis/ai_swarm
pip install -r requirements.txt

cd ../tool_service
pip install -r requirements.txt
```

#### 2. Environment Configuration

```bash
# Copy example environment
cp .env.example .env

# Edit .env with your credentials
nano .env
```

**Required environment variables:**
```
LLM_PROVIDER=openai          # or gemini, azure
LLM_MODEL=gpt-4
LLM_API_KEY=your_api_key_here
TOOL_SERVICE_URL=http://localhost:3000
```

#### 3. Start Services

```bash
# Terminal 1: Start Tool Service
cd apis/tool_service
python -m tool_service

# Terminal 2: Start AI Swarm Service
cd apis/ai_swarm
python -m ai_swarm

# Terminal 3: Start Frontend
cd ui
npm install
npm run dev
```

### Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f ai_swarm

# Stop services
docker-compose down
```

## Usage

### Web Interface (with Live SSE Progress)

1. Navigate to `http://localhost:5173`
2. Enter a company query: "Analyze TechCorp's market position for Series B funding"
3. Click "Start Research" 
4. **Live SSE Stream Begins**: Dashboard updates in real-time via Server-Sent Events
   - See each agent's status (orchestrator → specialists → devil's advocate → validator)
   - Watch progress bars update as agents execute
   - Monitor tool execution in real-time
   - Track findings as they appear
   - View confidence score building
5. Download PDF report when complete

### REST API

#### Stream Query with SSE (Real-time Progress)

The most powerful endpoint - get real-time updates as research progresses:

```bash
curl -N -X POST http://localhost:8000/api/query/stream \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the competitive position of Company X in the AI market?"
  }'
```

**The `-N` flag prevents buffering, enabling real-time SSE streaming**

**Response (Server-Sent Events - Live Stream):**
```
event: status
data: {"status": "started", "query": "What is the competitive position of Company X in the AI market?"}

event: agent
data: {"id": "orchestrator", "state": "active", "task": "Planning tasks...", "progress": 10}

event: progress
data: {"node": "orchestrator", "progress": 15, "detail": "sent llm request"}

event: progress
data: {"node": "orchestrator", "progress": 100, "detail": "completed"}

event: agent
data: {"id": "financial", "state": "active", "task": "Fetching market data...", "progress": 20}

event: agent
data: {"id": "web", "state": "active", "task": "Searching web...", "progress": 15}

event: agent
data: {"id": "domain", "state": "active", "task": "Querying knowledge base...", "progress": 10}

event: agent
data: {"id": "legal", "state": "active", "task": "Researching regulations...", "progress": 5}

event: tool
data: {"tool_name": "web_search", "status": "success", "output_length": 1245}

event: progress
data: {"node": "web_agent", "progress": 45, "detail": "tool executed: web_search"}

event: finding
data: {"tag": "competitor_info", "text": "CompetitorA has 45% market share in AI segment"}

event: metric
data: {"id": "sources", "value": 12}

event: metric
data: {"id": "claims", "value": 8}

event: agent
data: {"id": "financial", "state": "done", "task": "Market analysis complete", "progress": 100}

event: agent
data: {"id": "web", "state": "done", "task": "Web research complete", "progress": 100}

event: agent
data: {"id": "domain", "state": "done", "task": "Domain research complete", "progress": 100}

event: agent
data: {"id": "legal", "state": "done", "task": "Legal research complete", "progress": 100}

event: agent
data: {"id": "devil", "state": "active", "task": "Analyzing contradictions...", "progress": 80}

event: agent
data: {"id": "devil", "state": "done", "task": "Critique complete", "progress": 100}

event: agent
data: {"id": "validator", "state": "active", "task": "Validating claims...", "progress": 75}

event: confidence
data: {"value": 82}

event: agent
data: {"id": "validator", "state": "done", "task": "Validation complete", "progress": 100}

event: agent
data: {"id": "synthesis", "state": "active", "task": "Rendering final report PDF…", "progress": 80}

event: report
data: {"status": "started", "query": "What is the competitive position of Company X in the AI market?"}

event: report
data: {"status": "ready", "query": "What is the competitive position of Company X in the AI market?"}

event: agent
data: {"id": "synthesis", "state": "done", "task": "Report ready — full PDF generated", "progress": 100}

event: complete
data: {"query": "What is the competitive position of Company X in the AI market?", "is_valid": true, "confidence": "high", "agent_statuses": {"financial": "success", "web": "success", "domain": "partial", "legal": "success"}, "validated_answer": "Company X holds a strong position...", "agent_failures": []}

:stream-closed
```

**Key SSE Features:**
- ✅ Real-time agent status updates
- ✅ Per-node progress tracking (0-100%)
- ✅ Tool execution monitoring
- ✅ Live findings and metrics
- ✅ Confidence score updates
- ✅ Report generation status
- ✅ No polling required - persistent HTTP connection

event: agent
data: {"id": "orchestrator", "state": "active", "task": "Planning tasks...", "progress": 10}

event: agent
data: {"id": "financial", "state": "active", "task": "Fetching market data...", "progress": 30}

event: report
data: {"status": "ready", "query": "..."}

event: complete
data: {"query": "...", "is_valid": true, "confidence": "high", ...}
```

#### Get Report PDF

```bash
curl -X GET "http://localhost:8000/api/report?query=YourQuery" \
  -H "Accept: application/pdf" \
  > report.pdf
```

#### Synchronous Query

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Your research query"}'
```

**Response:**
```json
{
  "query": "...",
  "orchestrator_plan": "...",
  "validated_answer": "...",
  "is_valid": true,
  "confidence": "high",
  "agent_statuses": {
    "financial": "success",
    "domain": "success",
    "web": "partial",
    "legal": "success"
  },
  "agent_failures": [],
  "devils_critique": "..."
}
```

## API Documentation

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service health check |
| POST | `/api/query/stream` | Stream research with SSE |
| GET | `/api/query/stream` | Stream research (query param) |
| POST | `/api/report` | Get PDF report |
| GET | `/api/report` | Get PDF report (query param) |
| POST | `/api/query` | Synchronous research |

### Tool Service Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service health check |
| GET | `/tools` | List available tools |
| POST | `/tool/{tool_name}` | Execute a tool |

## Configuration

### LLM Provider Selection

**OpenAI:**
```
LLM_PROVIDER=openai
LLM_MODEL=gpt-4
LLM_API_KEY=sk-...
```

**Google Gemini:**
```
LLM_PROVIDER=gemini
LLM_MODEL=gemini-pro
LLM_API_KEY=...
```

**Azure AI Foundry:**
```
LLM_PROVIDER=openai
LLM_MODEL=gpt-4
LLM_BASE_URL=https://your-deployment.openai.azure.com/
LLM_API_KEY=...
```

**Open-source (Jarvis Labs):**
```
LLM_PROVIDER=openai
LLM_MODEL=gemma-4-e2b-it
LLM_BASE_URL=https://jarvis-labs-api-endpoint
LLM_API_KEY=...
```

### Advanced Configuration

```bash
# LLM temperature (creativity level)
LLM_TEMPERATURE=1.0              # 0.0 = deterministic, 2.0 = creative

# Retry behavior
LLM_MAX_RETRIES=2

# Tool service timeout
TOOL_SERVICE_TIMEOUT=30          # seconds

# Logging level
LOG_LEVEL=info                   # debug, info, warning, error
```

## Performance & Scaling

### Rate Limiting Considerations

**Challenge:** Parallel execution of 4-5 specialist agents + Devil's Advocate + Validator creates simultaneous LLM requests, risking rate limiting.

**Solutions Implemented:**

1. **Staggered Tool Execution**
   - Tool service queues requests to prevent overwhelming external APIs
   - Implements per-tool rate limit tracking

2. **Retry Logic with Exponential Backoff**
   ```python
   max_retries: int = 2
   backoff_factor: float = 1.2  # increases with each retry
   ```

3. **Request Batching**
   - Group similar requests where possible
   - Reduce redundant API calls

4. **Circuit Breaker Pattern**
   - Fail gracefully when rate limits hit
   - Fall back to cached data when available

5. **Graceful Degradation**
   - Mark agent as `PARTIAL` if non-critical tools fail
   - Continue with available data rather than full failure

### Optimization Tips

```bash
# Monitor tool execution
docker-compose logs tool_service | grep "tool executed"

# Set aggressive caching
CACHE_TTL=3600                  # Cache results for 1 hour

# Implement tool service scaling
# Scale tool_service horizontally for high-traffic scenarios
```

### Performance Monitoring

- **SSE Progress**: Real-time agent metrics on dashboard
- **Tool Metrics**: Track success/failure rates per tool
- **LLM Metrics**: Monitor token usage and latency
- **Pipeline Metrics**: End-to-end execution time

## Components Deep Dive

### Orchestrator Agent

**Role:** Query decomposition and task planning

**Process:**
1. Receives natural language query
2. Analyzes required research domains
3. Generates 5-8 specific, actionable tasks per specialist
4. Returns structured task list

**Example Decomposition:**
```
Query: "Is TechCorp a good Series B investment?"

Financial Tasks:
  - Get last 3 quarters of revenue and growth rate
  - Check cash runway and burn rate
  - Analyze unit economics if available

Founder Tasks:
  - Identify CEO and founding team
  - Research previous startup exits
  - Check track record in this industry

Market Tasks:
  - Estimate TAM for their product category
  - Identify top 3 competitors
  - Check market growth rate

Legal Tasks:
  - Search for pending litigation
  - Check patent portfolio
  - Verify regulatory compliance
```

### Specialist Agents

#### Financial Analyst
- Market data retrieval
- Earnings report parsing
- Financial modeling and projections
- Unit economics analysis

#### Domain Expert
- Internal knowledge base queries
- Expert report retrieval
- Industry trend analysis
- Insider knowledge synthesis

#### Web Researcher
- Web search and content aggregation
- URL scraping and content extraction
- News monitoring and alerts
- Public record searches

#### Legal Analyst
- Case law research
- Statute lookup and compliance checks
- Patent database searches
- Regulatory framework analysis

### Devil's Advocate

**Role:** Critical analysis and gap identification

**Responsibilities:**
1. Cross-references agent findings for contradictions
2. Identifies missing critical data
3. Flags unsupported claims
4. Highlights methodological limitations
5. Produces comprehensive critique

**Output Example:**
```
Contradictions Found:
  - Financial agent reports $5M revenue, but web researcher found only $3M

Data Gaps:
  - Legal agent unable to find patent history (impacts IP risk assessment)
  - Customer sentiment data unavailable (critical for Series B)

Unsupported Claims:
  - "Market leading position" lacks specific market share data
```

### Validator Agent

**Role:** Claim validation and confidence scoring

**Process:**
1. Examines each finding from all agents
2. Attempts to find primary sources
3. Validates factual accuracy
4. Assigns confidence level (high/medium/low)
5. Identifies data gaps impact on final recommendation

**Confidence Scoring:**
- `high`: Multiple corroborating sources, recent data, expert consensus
- `medium`: Single source, partial data, some conflicting information
- `low`: Unverified claims, outdated data, significant gaps

## Monitoring & Debugging

### View Real-time Logs

```bash
# AI Swarm Service
docker-compose logs -f ai_swarm

# Tool Service
docker-compose logs -f tool_service

# Combined with timestamps
docker-compose logs -f --timestamps
```

### Health Checks

```bash
# Check all services
curl http://localhost:8000/health
curl http://localhost:3000/health

# List available tools
curl http://localhost:3000/tools
```

### Debug Mode

```bash
# Enable debug logging
LOG_LEVEL=debug docker-compose up

# Inspect specific tool execution
curl -X POST http://localhost:3000/tool/web_search \
  -H "Content-Type: application/json" \
  -d '{"args": ["Apple Inc financial performance"], "kwargs": {}}'
```

## Troubleshooting

### Rate Limiting Errors

**Symptoms:** `429 Too Many Requests` errors from LLM API

**Solution:**
1. Reduce parallel agent count (modify pipeline.py)
2. Add request queueing with delays
3. Switch to LLM provider with higher rate limits
4. Implement caching for repeated queries

### Tool Service Timeout

**Symptoms:** Tools taking too long, blocking pipeline

**Solution:**
```bash
# Increase timeout
TOOL_SERVICE_TIMEOUT=60

# Or scale tool service horizontally
docker-compose up -d --scale tool_service=3
```

### Memory Issues with Large Reports

**Solution:**
```bash
# Increase container memory
# In docker-compose.yml:
deploy:
  resources:
    limits:
      memory: 2G
```

### LLM Connection Errors

**Checklist:**
- ✅ API key is valid and not expired
- ✅ Network connectivity to LLM provider
- ✅ Correct LLM_BASE_URL if using custom endpoint
- ✅ Model name is supported by provider

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/improvement`)
3. Make your changes
4. Commit with clear messages (`git commit -m 'Add feature X'`)
5. Push to branch (`git push origin feature/improvement`)
6. Open a Pull Request

## Future Enhancements

- [ ] Caching layer for repeated queries
- [ ] Multi-language support
- [ ] Custom knowledge base integration
- [ ] Advanced visualization dashboards
- [ ] API rate limiting middleware
- [ ] Webhook support for async processing
- [ ] Advanced source attribution with citations
- [ ] Sentiment analysis visualization
- [ ] Competitive intelligence trending
- [ ] Custom agent creation framework

## Support

For issues, questions, or suggestions:
1. Check [DOCKER_SETUP.md](./DOCKER_SETUP.md) for deployment help
2. Review service-specific READMEs in `apis/ai_swarm/` and `apis/tool_service/`
3. Check logs: `docker-compose logs -f`
4. File an issue with detailed error messages and reproduction steps

---

**Built with:** LangGraph, FastAPI, React, Docker, OpenAI/Gemini/Azure AI
