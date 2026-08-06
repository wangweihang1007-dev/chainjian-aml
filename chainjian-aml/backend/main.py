"""FastAPI service entry point.

The service is supported both as ``main:app`` with uvicorn's ``--app-dir
backend`` and as ``backend.main:app`` from tests and IDEs.
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi import FastAPI

from api.alert import router as alert_router
from api.agent import router as agent_router
from api.evaluation import router as evaluation_router
from api.graph import router as graph_router
from api.graph_intelligence import router as graph_intelligence_router
from api.monitoring import router as monitoring_router
from api.report import router as report_router
from api.dashboard import router as dashboard_router
from api.materials import router as materials_router
from api.material_metrics import router as material_metrics_router
from api.auth import router as auth_router
from api.iteration import router as iteration_router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="ChainJian AML")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",
        "http://127.0.0.1:8501",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(alert_router)
app.include_router(agent_router)
app.include_router(evaluation_router)
app.include_router(graph_router)
app.include_router(graph_intelligence_router)
app.include_router(monitoring_router)
app.include_router(report_router)
app.include_router(dashboard_router)
app.include_router(materials_router)
app.include_router(material_metrics_router)
app.include_router(auth_router)
app.include_router(iteration_router)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "chainjian-aml"}
