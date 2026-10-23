from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.core.config import get_settings
from app.models.domain import ExtractRequest
from app.services.extractor import LLMExtractor, MockExtractor

router = APIRouter(prefix="/api/notices", tags=["notices"])


def extractor():
    settings = get_settings()
    return MockExtractor() if settings.extractor_mode == "mock" else LLMExtractor(settings.llm_provider, settings.llm_model, settings.llm_api_key, settings.llm_base_url)


@router.post("/extract")
def extract_json(request: ExtractRequest):
    return extractor().extract(request.text)


@router.post("/extract-file")
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
    return extractor().extract(text)
