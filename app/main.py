import logging

from fastapi import FastAPI

from app.database import Base, engine
from app.routers import sheets, team
from app.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(level=logging.INFO)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Sheet Scheduler")

app.include_router(sheets.router)
app.include_router(team.router)


@app.on_event("startup")
def on_startup():
    start_scheduler()


@app.on_event("shutdown")
def on_shutdown():
    stop_scheduler()


@app.get("/")
def health_check():
    return {"status": "ok"}
