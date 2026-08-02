"""FastAPI service entry point."""

from fastapi import FastAPI

from api.alert import router as alert_router
from api.agent import router as agent_router
from api.evaluation import router as evaluation_router
from api.graph import router as graph_router
from api.graph_intelligence import router as graph_intelligence_router
from api.monitoring import router as monitoring_router
from api.report import router as report_router
from api.dashboard import router as dashboard_router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="ChainJian AML")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(alert_router)
app.include_router(agent_router)
app.include_router(evaluation_router)
app.include_router(graph_router)
app.include_router(graph_intelligence_router)
app.include_router(monitoring_router)
app.include_router(report_router)
app.include_router(dashboard_router)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "chainjian-aml"}
