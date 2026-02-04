"""FastAPI application — entry point for the content autopilot system."""

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from db import create_tables
from orchestrator import Orchestrator
from routes import router, set_orchestrator, set_skill_manager
from dashboard import dashboard_router
from skills.manager import SkillManager

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

orchestrator = Orchestrator()
skill_manager = SkillManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    logger.info("=" * 70)
    logger.info("Autopilot by Kairox AI - Starting Up")
    logger.info("=" * 70)
    logger.info("Mode: %s", "DEMO MODE" if settings.demo_mode else "PRODUCTION MODE")
    logger.info("Port: %d", settings.port)
    logger.info("Daily cost limit: $%.2f", settings.daily_cost_limit)

    logger.info("Creating database tables...")
    await create_tables()

    logger.info("Loading skills...")
    skills = skill_manager.load_all()
    logger.info("Loaded %d skills", len(skills))

    # Conditional seeding in demo mode
    if settings.demo_mode and settings.seed_on_startup:
        logger.info("Demo mode enabled - seeding demo data...")
        try:
            from scripts.seed_demo_data import seed_demo_data
            await seed_demo_data()
            logger.info("✓ Demo data seeded successfully")
        except Exception as e:
            logger.error("Failed to seed demo data: %s", e)
            logger.error("Continuing without demo data...")

    set_orchestrator(orchestrator)
    set_skill_manager(skill_manager)

    logger.info("Starting orchestrator...")
    await orchestrator.start(demo_mode=settings.demo_mode)

    logger.info("=" * 70)
    logger.info("Autopilot by Kairox AI is running on http://localhost:%d", settings.port)
    logger.info("Mode: %s", "DEMO (manual triggers only)" if settings.demo_mode else "PRODUCTION (auto-scheduling)")
    logger.info("=" * 70)
    yield

    # Shutdown
    logger.info("Stopping orchestrator...")
    await orchestrator.stop()
    logger.info("Shutdown complete")


app = FastAPI(
    title="Autopilot by Kairox AI",
    description="Autonomous content arbitrage system",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard_router)
app.include_router(router)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=settings.port, reload=True)
