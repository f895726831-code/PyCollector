"""
FastAPI router builder.

Provides a helper to compose modular API routers with prefix + tag
registration, following the pattern of including domain-specific
routers into a central API router.
"""

from fastapi import APIRouter


def build_api_router(
    routers: list[tuple[APIRouter, str, str]],
) -> APIRouter:
    """Build a central API router from a list of domain routers.

    Parameters
    ----------
    routers:
        List of ``(router, prefix, tag)`` tuples.  Each domain router
        is included under *prefix* and tagged with *tag*.

    Returns
    -------
    APIRouter
        The composed router ready to be included in a FastAPI app.

    Example
    -------
    >>> from pycollector.api.router import build_api_router
    >>> from myapp.api.routes import jobs, results
    >>> api_router = build_api_router([
    ...     (jobs.router, "/api/v1", "jobs"),
    ...     (results.router, "/api/v1", "results"),
    ... ])
    """
    api_router = APIRouter()
    for router, prefix, tag in routers:
        api_router.include_router(router, prefix=prefix, tags=[tag])
    return api_router