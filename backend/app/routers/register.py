"""Application assembly hook for the shared FastAPI ``main.py``."""

from typing import Any


def register_wenhao_routers(app: Any) -> None:
    """Register the integrated research, execution, and deliverable routes."""

    from backend.app.deliverables.repository import SqlAlchemyDeliverableRepository
    from backend.app.deliverables.service import DeliverableService
    from backend.db import SessionLocal

    from .execution import router as execution_router
    from .deliverables import router as deliverables_router
    from .research import router as research_router

    app.state.deliverable_service = DeliverableService(
        SqlAlchemyDeliverableRepository(SessionLocal)
    )
    app.include_router(research_router)
    app.include_router(execution_router)
    app.include_router(deliverables_router)
