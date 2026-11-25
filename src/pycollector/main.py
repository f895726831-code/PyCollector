"""
FastAPI application factory.

Provides :func:`create_app` — a one-call factory that wires together
the FastAPI app, exception handlers, API router, and scheduler
lifespan management.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from pycollector.api.router import build_api_router
from pycollector.core.errors import register_exception_handlers
from pycollector.core.settings import get_settings


def create_app(
    *,
    api_routers: list | None = None,
    lifespan_handlers: list | None = None,
    title: str | None = None,
    debug: bool | None = None,
) -> FastAPI:
    """Create and configure a FastAPI application.

    Parameters
    ----------
    api_routers:
        List of ``(router, prefix, tag)`` tuples for ``build_api_router``.
    lifespan_handlers:
        Optional list of async context managers for startup/shutdown.
    title:
        Override the app title (default: from settings).
    debug:
        Override debug mode (default: from settings).

    Returns
    -------
    FastAPI
        A fully configured application instance.
    """
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Run custom lifespan handlers
        if lifespan_handlers:
            for handler in lifespan_handlers:
                async with handler(app):
                    pass
        yield

    app = FastAPI(
        title=title or settings.app_name,
        debug=debug if debug is not None else settings.app_debug,
        lifespan=lifespan,
    )

    # Register API routes
    if api_routers:
        api_router = build_api_router(api_routers)
        app.include_router(api_router)

    # Register exception handlers
    register_exception_handlers(app)

    return app