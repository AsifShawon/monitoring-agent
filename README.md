# 🔍 LinkedIn & Website Monitoring System

An intelligent monitoring system that tracks changes on LinkedIn profiles, companies, and websites using **LangGraph** workflows, **Gemini AI** analysis, and automated notifications.

# Approach

**Architecture**: FastAPI REST API + Celery task queue + MongoDB + LangGraph orchestration

**Workflow**: User creates target → Celery scheduler triggers scraping → LangGraph coordinates agents → Store changes + Send notifications

**Key Components**:
- **Scraper Agent**: Scrapingdog API for LinkedIn data extraction
- **Analyzer Agent**: LangChain + Gemini AI for intelligent change detection
- **Notifier Agent**: Email alerts with HTML templates
- **Coordinator**: LangGraph state machine orchestrating the workflow

## Architecture

### Tech Stack

- **FastAPI**: REST API with async MongoDB
- **LangGraph**: State machine for agent orchestration
- **LangChain + Gemini**: AI-powered change analysis
- **Celery + Redis**: Distributed task queue and scheduling
- **MongoDB**: NoSQL database for users, targets, and changes
- **Scrapingdog API**: LinkedIn data extraction

### Tech Stack

- **LangGraph**: Workflow orchestration
- **LangChain**: AI framework with Google Generative AI integration
- **Gemini Pro**: LLM for change analysis
- **FastAPI**: REST API server
- **Celery + Redis**: Task queue and scheduler
- **MongoDB**: Database for users, targets, and changes
- **Scrapingdog API**: LinkedIn profile/company scraping
- **Playwright/Selenium**: Website scraping
- **SMTP**: Email notifications

## Project Structure

```
monitoring-agent/
├── app/
│   ├── agents/
│   │   ├── coordinator.py         
│   │   ├── analyzer.py            
│   │   ├── notifier.py            
│   │   ├── scraper.py             
│   │   ├── scraper_agent.py       
│   │   ├── scheduler_agent.py     
│   │   └── schedule.py            
│   ├── routes_complete.py         
│   ├── database.py                
│   ├── models.py                  
│   ├── config.py
│   └── main.py                                   
├── run_all_services.sh            # (tmux)
├── requirements.txt               
└── .env.example                   

```
## Prerequisites

- Python 3.10+, MongoDB, Redis
- Scrapingdog API key, Gemini API key, SMTP credentials

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with API keys

# Start services (FastAPI + Celery Worker + Beat)
./run_server.sh

# Test API
curl http://localhost:8000/health
```

Visit http://localhost:8000/docs for interactive API documentation, or use **Postman** to test endpoints.

## API Usage

**Testing with Postman**: Import endpoints and test all API operations with Postman for a better testing experience.

```bash
# 1. User signup
POST /users/signup

# 2. Create monitoring target
POST /users/{user_id}/targets
{
  "url": "https://www.linkedin.com/in/example/",
  "type": "linkedin_profile",
  "frequency": "daily"
}

# 3. View targets and changes
GET /users/{user_id}/targets
GET /targets/{target_id}/changes
GET /users/{user_id}/changes

# 4. Manage targets
DELETE /targets/{target_id}
```

## How It Works

1. User creates target via REST API
2. Celery Beat scheduler checks due targets periodically
3. Scraper Agent triggers LangGraph workflow:
   - **Scraper Node**: Fetches data (Scrapingdog API)
   - **Analyzer Node**: Compares with previous data (Gemini AI)
   - **Notifier Node**: Sends email if significant changes
4. Changes stored in MongoDB, user notified via email

## Testing

```bash
# Test individual agents
python app/agents/scraper.py
python app/agents/analyzer.py
python app/agents/coordinator.py

```

## Implementation Highlights

- **Simplified Routes**: Kept only 9 essential endpoints (user signup, target CRUD, change history, health)
- **API-Only Scraping**: Removed selenium/headless browser, using Scrapingdog API for reliability
- **LangGraph State Machine**: Clean orchestration with conditional routing based on change severity
- **Async MongoDB**: Per-URL databases for scalable change tracking
- **Production-Ready**: Celery for distributed tasks, proper error handling, fallback modes

---

Built with LangGraph, LangChain, FastAPI, and MongoDB
