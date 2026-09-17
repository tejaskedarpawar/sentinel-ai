from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routers import health, employees, alerts, stats, graph

app = FastAPI(
    title="Sentinel AI",
    description="Privacy-preserving insider data exfiltration detection — API",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(employees.router)
app.include_router(alerts.router)
app.include_router(stats.router)
app.include_router(graph.router)


@app.on_event("startup")
def on_startup():
    init_db()
