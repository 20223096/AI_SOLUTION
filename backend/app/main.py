from fastapi import FastAPI

from app.api import experiments, impact, noise, notices, scenarios, schedules
from app.core.config import get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name, version=settings.model_version, description="행정 참고용 PoC. 법적 허가·준수 인증이 아닙니다.")


@app.get("/api/health")
def health():
    return {"status": "ok", "model_version": settings.model_version, "extractor_mode": settings.extractor_mode}


for router in (scenarios.router, notices.router, noise.router, impact.router, schedules.router, experiments.router):
    app.include_router(router)
