from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.core.config import get_settings
from app.models.domain import ExtractRequest
from app.models.responses import NoticeExtractResponse
from app.services.extractor import LLMExtractionError, LLMExtractor, MockExtractor

router = APIRouter(prefix="/api/notices", tags=["notices"])


def extractor():
    settings = get_settings()
    return MockExtractor() if settings.extractor_mode == "mock" else LLMExtractor(settings.llm_provider, settings.llm_model, settings.llm_api_key, settings.llm_base_url)


@router.post("/extract", response_model=NoticeExtractResponse)
def extract_json(request: ExtractRequest):
    try:
        return extractor().extract(request.text)
    except LLMExtractionError as exc:
        raise HTTPException(exc.http_status, {"category": exc.category, "message": exc.message}) from exc


@router.post("/extract-file", response_model=NoticeExtractResponse)
async def extract_file(file: UploadFile = File(...)):
    raw = await file.read()
    if file.content_type == "application/pdf":
        try:
            from pypdf import PdfReader
            import io
            text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(raw)).pages)
        except ImportError as exc:
            raise HTTPException(503, "PDF support requires pypdf") from exc
    elif file.content_type and (file.content_type.startswith("text/") or file.filename.endswith(".txt")):
        text = raw.decode("utf-8")
    else:
        raise HTTPException(415, "Only UTF-8 text or text-extractable PDF is supported")
    if not text.strip():
        raise HTTPException(422, "No extractable text")
    try:
        return extractor().extract(text)
    except LLMExtractionError as exc:
        raise HTTPException(exc.http_status, {"category": exc.category, "message": exc.message}) from exc
