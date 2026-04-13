from __future__ import annotations
from app.services.cache.response_cache import response_cache
"""
Service container.

Centralizes access to service-layer utilities so routers
do not create tight coupling between modules.

This also prevents circular imports across:

    routers
    query services
    card builders
    cache
"""




class ServiceContainer:
    """
    Lightweight dependency container.

    In the future this can evolve into a full DI system,
    but for now it simply exposes shared services.
    """

    def __init__(self) -> None:
        self.cache = response_cache


# global container instance
services = ServiceContainer()