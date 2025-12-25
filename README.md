# NetGuard AI - MVP

Full-stack AI-assisted network monitoring and auto-remediation platform.

## Architecture

- **Backend**: FastAPI (Python)
- **Database**: PostgreSQL + TimescaleDB
- **Agents**: Monitor, Diagnoser, Fix (Python)
- **Frontend**: React + TailwindCSS (Vite)
- **Deployment**: Docker Compose

## Requirements

- Docker & Docker Compose
- Python 3.11+ (for local dev)
- Node.js 18+ (for local dev)

## Setup & Running

1. **Start the stack**
   ```bash
   docker-compose up --build
   ```

2. **Access the application**
   - Frontend: [http://localhost:3000](http://localhost:3000)
   - Backend API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)

3. **Default Credentials** (First run creates these via Signup if not seeded)
   - Go to /docs and use the Signup endpoint to create a user.
   
## Development

- Backend: running on port 8000
- Frontend: running on port 3000 (mapped to 80 in container)

## Agents

To run agents locally:
```bash
cd agents
pip install -r requirements.txt
python monitor_agent.py
```
(You need to set `API_URL` env var if running outside docker network)

## Auto-Fix Example

1. Enable 'auto-fix' for a Site.
2. If an alert with 'Offline' status is detected, the Diagnoser will flag it.
3. FixAgent will attempt to resolve it.
