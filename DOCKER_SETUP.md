# Docker Setup Guide

This guide explains how to build and run the entire ResearchSwarm application using Docker Compose.

## Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- An API key for your chosen LLM provider (OpenAI, Google Gemini, etc.)

## Quick Start

### 1. Clone and Setup

```bash
cd /path/to/Hackathon_Microsoft
```

### 2. Configure Environment

Copy the example environment file and update with your credentials:

```bash
cp .env.example .env
```

Edit `.env` and add your LLM API key:

```bash
LLM_PROVIDER=openai
LLM_MODEL=gpt-4
LLM_API_KEY=sk-your-actual-api-key-here
```

### 3. Build and Run

```bash
# Build all services
docker-compose build

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop all services
docker-compose down
```

## Services

The Docker Compose setup includes three services:

### Tool Service (port 3000)
- Provides tool registry and execution for AI agents
- Endpoints: `/health`, `/tools`, `/tool/{tool_name}`
- No special configuration needed

### AI Swarm Service (port 8000)
- Main research orchestration service
- REST API: `/api/query`, `/api/query/stream`, `/api/report`
- Requires LLM configuration via environment variables
- Depends on: Tool Service

### Frontend (port 5173)
- React UI for the research swarm
- Access at: http://localhost:5173
- Communicates with AI Swarm Service on port 8000
- Depends on: AI Swarm Service

## Environment Variables

### Required
- `LLM_API_KEY` - API key for your LLM provider

### LLM Configuration
- `LLM_PROVIDER` - Provider name (openai, gemini) - default: openai
- `LLM_MODEL` - Model identifier - default: gpt-4
- `LLM_TEMPERATURE` - Temperature (0-1) - default: 1.0

### Optional
- `LLM_BASE_URL` - Custom base URL for LLM provider
- `LLM_MAX_RETRIES` - Max retries for LLM - default: 2
- `VITE_API_BASE_URL` - Frontend API endpoint - default: http://localhost:8000
- `LOG_LEVEL` - Logging level (info, debug, etc.) - default: info

## Common Commands

### View service logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f ai_swarm
docker-compose logs -f tool_service
docker-compose logs -f frontend
```

### Rebuild a service
```bash
docker-compose build --no-cache ai_swarm
```

### Run services in foreground
```bash
docker-compose up
```

### Remove all containers and volumes
```bash
docker-compose down -v
```

### Check service health
```bash
docker-compose ps
```

## Testing the Services

### Test Tool Service
```bash
curl http://localhost:3000/health
curl http://localhost:3000/tools
```

### Test AI Swarm Service
```bash
curl http://localhost:8000/health

# Stream a query
curl -X POST http://localhost:8000/api/query/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the market size for AI in healthcare?"}'
```

### Access Frontend
Open your browser to: http://localhost:5173

## Troubleshooting

### Service won't start
```bash
# Check logs
docker-compose logs service_name

# Rebuild
docker-compose build --no-cache

# Restart
docker-compose restart
```

### LLM connection errors
- Verify `LLM_API_KEY` is correct in `.env`
- Check `LLM_PROVIDER` is valid (openai, gemini)
- Verify network connectivity to LLM provider

### Port already in use
If ports 3000, 5173, or 8000 are already in use:

```bash
# Option 1: Change ports in docker-compose.yml
# Example: "3001:3000" to use host port 3001

# Option 2: Kill process using port
lsof -i :3000
kill -9 <PID>
```

### Frontend not connecting to backend
- Check `.env` for `VITE_API_BASE_URL`
- Verify ai_swarm service is running and healthy
- Check browser console for CORS errors
- Verify network connectivity between containers

### Database/Volume issues
```bash
# Clean up volumes
docker-compose down -v

# Rebuild
docker-compose build

# Start fresh
docker-compose up -d
```

## Development Workflow

### Making changes to ai_swarm service
```bash
# Rebuild just this service
docker-compose build ai_swarm

# Restart
docker-compose restart ai_swarm

# View logs
docker-compose logs -f ai_swarm
```

### Making changes to frontend
```bash
# Rebuild and restart
docker-compose build frontend
docker-compose restart frontend
```

## Performance Tips

1. **Use .dockerignore files** - Exclude unnecessary files from build context
2. **Multi-stage builds** - Already implemented in frontend Dockerfile
3. **Layer caching** - Order Dockerfile commands by change frequency
4. **Resource limits** - Add to docker-compose.yml if needed:
   ```yaml
   deploy:
     resources:
       limits:
         cpus: '2'
         memory: 4G
   ```

## Production Deployment

### Use environment-specific configs
```bash
# Create production environment
cp .env.example .env.prod

# Run with specific compose file
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Reverse proxy (Nginx/Caddy)
- Route `/api/*` to port 8000 (AI Swarm)
- Route `/tools/*` to port 3000 (Tool Service)
- Route `/` to port 5173 (Frontend)

### Health checks
All services include health checks in the compose file. Check status:
```bash
docker-compose ps
```

## Monitoring

### Container metrics
```bash
docker stats

# Specific container
docker stats tool_service ai_swarm frontend
```

### Service logs
```bash
# Follow logs from service startup
docker-compose logs --since 5m ai_swarm

# Export logs to file
docker-compose logs > logs.txt
```

## Cleanup

### Remove all containers and volumes
```bash
docker-compose down -v
```

### Remove built images
```bash
docker-compose down -v --rmi all
```

### Clean up Docker system (careful!)
```bash
docker system prune -a --volumes
```

## Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [AI Swarm Service README](./apis/ai_swarm/README.md)
- [Tool Service README](./apis/tool_service/README.md)
