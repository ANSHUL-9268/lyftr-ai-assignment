"""
FastAPI application factory and configuration.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import init_db
from app.core.logging import setup_logging, get_logger
from app.api import webhook, messages, stats, health, metrics
from app.api.metrics import MetricsMiddleware, set_startup_time


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger = get_logger(__name__)
    logger.info("Starting application...")
    
    # Initialize database
    init_db()
    logger.info("Database initialized")
    
    # Record startup time for metrics
    set_startup_time()
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    
    # Setup logging
    setup_logging()
    logger = get_logger(__name__)
    
    # Create FastAPI app
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Production-style FastAPI service for ingesting WhatsApp-like messages",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add metrics middleware
    app.add_middleware(MetricsMiddleware)
    
    # Include routers
    app.include_router(webhook.router)
    app.include_router(messages.router)
    app.include_router(stats.router)
    app.include_router(health.router)
    app.include_router(metrics.router)
    
    logger.info(
        "Application created",
        extra={
            "extra_data": {
                "app_name": settings.app_name,
                "version": settings.app_version,
                "debug": settings.debug,
            }
        }
    )
    
    return app


# Create the application instance
app = create_app()
