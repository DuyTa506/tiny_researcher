# Quick Start Guide - Research Assistant v3.4

## 🚀 Quick Start (Docker - Recommended)

**One command to start everything:**

```bash
# Navigate to project
cd /home/duy/Downloads/duy_dev/tiny_researcher/backend

# Add your API key to .env
echo "OPENAI_API_KEY=your_key_here" > .env

# Start all services
docker compose -f docker/docker-compose.yml up -d

# Or use Makefile shortcut
make up
```

**Access:**
- API Documentation: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

See [DOCKER.md](DOCKER.md) for complete Docker guide.

---

## Manual Installation

### Prerequisites

- Python 3.10+
- MongoDB 7.0+ (or use Docker)
- Redis 7.0+ (or use Docker)
- OpenAI or Gemini API key

## Installation

### Option 1: Using pip (Recommended)

```bash
# 1. Clone and navigate to the project
cd /home/duy/Downloads/duy_dev/tiny_researcher/backend

# 2. Create virtual environment
python3 -m venv .venv

# 3. Activate virtual environment
source .venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. (Optional) Install development dependencies
pip install -r requirements-dev.txt
```

### Option 2: Using uv (Faster)

```bash
# 1. Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Navigate to project
cd /home/duy/Downloads/duy_dev/tiny_researcher/backend

# 3. Create virtual environment and install
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt

# 4. (Optional) Install development dependencies
uv pip install -r requirements-dev.txt
```

## Configuration

```bash
# 1. Create .env file (if not exists)
cat > .env << 'EOF'
# LLM API Keys (at least one required)
OPENAI_API_KEY=your_openai_key_here
GEMINI_API_KEY=your_gemini_key_here

# Database
MONGO_URL=mongodb://localhost:27017
MONGO_DB_NAME=research_assistant

# Cache
REDIS_URL=redis://localhost:6379/0

# App Settings
ENVIRONMENT=development
PROJECT_NAME="Research Assistant"
VERSION=3.4.0
EOF

# 2. Edit .env and add your actual API keys
nano .env
```

## Start Services

```bash
# Start MongoDB
docker run -d -p 27017:27017 --name mongo mongo:7

# Start Redis
docker run -d -p 6379:6379 --name redis redis:7

# Verify services are running
docker ps
```

## Run the Application

### Option 1: CLI Mode

```bash
# Activate environment
source .venv/bin/activate

# Load environment variables
export $(grep -v '^#' .env | xargs)

# Run CLI
python research_cli.py

# Options:
# --mock              Use mock LLM (no API key needed)
# --user USER_ID      Set custom user ID
```

**CLI Commands:**
| Command | Description |
|---------|-------------|
| `<topic>` | Start research on a topic |
| `ok` / `yes` | Confirm and proceed |
| `cancel` | Cancel current operation |
| `add <text>` | Add to plan |
| `remove <text>` | Remove from plan |
| `/ask <question>` | Ask LLM with streaming |
| `/explain <topic>` | Explain topic with streaming |
| `help` | Show help |
| `quit` | Exit application |

### Option 2: API Mode

```bash
# Activate environment
source .venv/bin/activate

# Load environment variables
export $(grep -v '^#' .env | xargs)

# Start API server
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

**Access Points:**
- **Swagger UI**: http://localhost:8000/docs (Interactive API documentation)
- **ReDoc**: http://localhost:8000/redoc (Alternative documentation)
- **Health Check**: http://localhost:8000/health

**Quick API Test:**
```bash
# Health check
curl http://localhost:8000/health

# Start conversation
curl -X POST http://localhost:8000/api/v1/conversations \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test_user"}'

# Send message (replace {id} with conversation_id from above)
curl -X POST http://localhost:8000/api/v1/conversations/{id}/messages \
  -H "Content-Type: application/json" \
  -d '{"message": "transformer models"}'
```

## Example Workflows

### CLI Research Session
```bash
$ python research_cli.py

🔬 RESEARCH ASSISTANT v3.0
Intelligent Paper Discovery

You: transformer models

🤖 Agent: Here's my research plan:

**Mode:** FULL
**Phases:** planning, execution, persistence, analysis, pdf_loading,
            summarization, clustering, writing

**Steps:**
  1. Search arXiv - Queries: transformer, attention mechanism
  2. Search HuggingFace - Queries: transformer models
  ...

Proceed? (yes/no/edit)

You: yes

⏳ Planning...
⏳ Execution... (99 papers collected)
⏳ Analysis... (25 relevant papers)
⏳ PDF Loading... (8 high-value papers)
⏳ Summarization...
⏳ Clustering... (4 themes)
⏳ Writing...
✅ Complete!

📊 Results
Topic: transformer models
Papers Found: 99
Relevant: 25
High Relevance: 8
Clusters: 4

[Report preview shown]

You: /ask What is the difference between BERT and GPT?

🤖 Agent: [Streaming response...]
BERT (Bidirectional Encoder Representations from Transformers) is designed
for understanding tasks...

You: quit
Goodbye!
```

### API with Python
```python
import asyncio
import httpx

async def research_example():
    async with httpx.AsyncClient(timeout=120.0) as client:
        # 1. Start conversation
        resp = await client.post(
            "http://localhost:8000/api/v1/conversations",
            json={"user_id": "researcher1"}
        )
        conv_id = resp.json()["conversation_id"]
        print(f"Conversation: {conv_id}")

        # 2. Send research topic
        resp = await client.post(
            f"http://localhost:8000/api/v1/conversations/{conv_id}/messages",
            json={"message": "transformer models"}
        )
        data = resp.json()
        print(f"State: {data['state']}")  # reviewing
        print(f"Plan steps: {len(data['plan']['steps'])}")

        # 3. Approve plan
        resp = await client.post(
            f"http://localhost:8000/api/v1/conversations/{conv_id}/messages",
            json={"message": "yes"}
        )
        result = resp.json()["result"]
        print(f"Papers found: {result['unique_papers']}")
        print(f"Relevant papers: {result['relevant_papers']}")

asyncio.run(research_example())
```

### WebSocket with JavaScript
```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/ws/my-conversation');

ws.onopen = () => {
  console.log('Connected');

  // Send message
  ws.send(JSON.stringify({
    type: 'message',
    content: 'transformer models'
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  switch(data.type) {
    case 'connected':
      console.log('Conversation started:', data.data.conversation_id);
      break;
    case 'response':
      console.log('State:', data.data.state);
      console.log('Message:', data.data.message);
      break;
    case 'progress':
      console.log('Progress:', data.data.phase, data.data.message);
      break;
    case 'stream_chunk':
      process.stdout.write(data.data.chunk);
      break;
  }
};
```

## Running Tests

```bash
# Activate environment
source .venv/bin/activate
export $(grep -v '^#' .env | xargs)

# API tests (requires API server running)
# Terminal 1: Start server
uvicorn src.api.main:app --host 0.0.0.0 --port 8000

# Terminal 2: Run tests
python scripts/test_api.py

# CLI tests (stop API server first - Qdrant conflict)
pkill -f "uvicorn src.api.main:app"
python scripts/test_cli.py

# Full pipeline test
python scripts/test_phase_1_2.py

# Conversation interface test
python scripts/test_phase_4.py
```

## Troubleshooting

### "Module not found" errors
```bash
# Ensure you're in the correct directory
cd /home/duy/Downloads/duy_dev/tiny_researcher/backend

# Ensure venv is activated
source .venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### "LLM service unavailable"
```bash
# Check if API key is set
echo $OPENAI_API_KEY  # or GEMINI_API_KEY

# If empty, load from .env
export $(grep -v '^#' .env | xargs)

# Verify it's now set
echo $OPENAI_API_KEY
```

### "Redis connection failed"
```bash
# Check if Redis is running
docker ps | grep redis

# If not running, start it
docker run -d -p 6379:6379 --name redis redis:7

# Test connection
docker exec -it redis redis-cli ping
# Should return: PONG
```

### "MongoDB connection failed"
```bash
# Check if MongoDB is running
docker ps | grep mongo

# If not running, start it
docker run -d -p 27017:27017 --name mongo mongo:7

# Test connection
docker exec -it mongo mongosh --eval "db.version()"
```

### "Qdrant storage locked"
This occurs when running CLI and API simultaneously (both use embedded Qdrant).

**Solution:**
```bash
# Stop the API server
pkill -f "uvicorn src.api.main:app"

# Then run CLI
python research_cli.py
```

Or vice versa - only run one at a time.

### Port 8000 already in use
```bash
# Find process using port 8000
lsof -i :8000

# Kill the process
kill -9 <PID>

# Or use a different port
uvicorn src.api.main:app --port 8001
```

## Project Structure

```
backend/
├── src/
│   ├── api/              # FastAPI application
│   │   ├── routes/       # REST & WebSocket endpoints
│   │   │   ├── conversation.py    # Conversation API + SSE
│   │   │   ├── websocket.py       # WebSocket endpoint
│   │   │   ├── planner.py         # Plan CRUD
│   │   │   └── sources.py         # Source processing
│   │   └── main.py       # App entry point
│   ├── cli/              # CLI interface (Rich-based)
│   │   ├── app.py        # CLI application
│   │   └── display.py    # Display components
│   ├── conversation/     # Dialogue management
│   │   ├── dialogue.py   # DialogueManager
│   │   ├── context.py    # ConversationContext
│   │   ├── intent.py     # Intent classifier
│   │   └── clarifier.py  # Query clarifier
│   ├── core/             # Core models & config
│   ├── planner/          # Research planning
│   │   ├── adaptive_planner.py    # Adaptive planning
│   │   ├── executor.py            # Plan execution
│   │   └── service.py             # Planner service
│   ├── research/         # Pipeline & analysis
│   │   ├── pipeline.py            # Main pipeline
│   │   ├── analysis/              # Analysis services
│   │   └── synthesis/             # Report generation
│   ├── storage/          # MongoDB & vector store
│   ├── tools/            # Tool registry & cache
│   └── memory/           # Memory management
├── scripts/              # Test scripts
├── docs/                 # Documentation
├── requirements.txt      # Python dependencies
├── requirements-dev.txt  # Development dependencies
├── research_cli.py       # CLI entry point
└── .env                  # Configuration (create from template)
```

## Documentation

- **QUICKSTART.md** - This file
- **docs/phase_5_api_integration.md** - API implementation guide
- **docs/system_design.md** - Architecture overview
- **docs/checklist.md** - Feature checklist
- **docs/process_track.md** - Development progress
- **CLAUDE.md** - AI agent guide

## API Endpoints Reference

### REST API
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/v1/conversations` | POST | Start conversation |
| `/api/v1/conversations/{id}` | GET | Get conversation state |
| `/api/v1/conversations/{id}/messages` | POST | Send message |
| `/api/v1/conversations/{id}` | DELETE | Delete conversation |
| `/api/v1/conversations/{id}/stream` | GET | SSE stream (real-time) |

### WebSocket
| Endpoint | Description |
|----------|-------------|
| `/api/v1/ws/{conversation_id}` | Real-time bidirectional communication |

## Next Steps

1. **Try the CLI**: `python research_cli.py`
2. **Explore the API**: Visit http://localhost:8000/docs
3. **Build a Frontend**: Use the WebSocket API
4. **Production Deploy**:
   - Add authentication
   - Set up monitoring
   - Configure proper CORS
   - Use managed MongoDB/Redis

## Support & Resources

- **Interactive API Docs**: http://localhost:8000/docs
- **Full API Guide**: docs/phase_5_api_integration.md
- **Architecture**: docs/system_design.md
- **Test Examples**: scripts/ directory

---
**Version:** v3.4
**Status:** ✅ Production Ready (needs hardening)
**Package Manager:** pip / uv
