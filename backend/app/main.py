from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import experiments, impact, noise, notices, prd, public_data, scenarios, schedules
from app.core.config import get_settings
from app.models.responses import HealthResponse

settings = get_settings()
app = FastAPI(title=settings.app_name, version=settings.model_version, description="행정 참고용 PoC. 법적 허가·준수 인증이 아닙니다.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Accept", "Content-Type"],
)


@app.get("/api/health", response_model=HealthResponse)
def health():
    return {"status": "ok", "model_version": settings.model_version, "extractor_mode": settings.extractor_mode}


for router in (scenarios.router, notices.router, noise.router, impact.router, schedules.router, experiments.router, public_data.router, prd.router):
    app.include_router(router)
