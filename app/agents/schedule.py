from celery import Celery

celery_app = Celery(
    "monitoring_agent",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0"
)

celery_app.conf.timezone = "UTC"
celery_app.conf.beat_schedule = {
    "run-scheduler-every-minute": {
        "task": "app.agents.scheduler_agent.run_scheduler",
        "schedule": 600.0,  
    },
}

celery_app.conf.imports = (
    'app.agents.scheduler_agent',
    'app.agents.scraper_agent',
)
