from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import unquote

import httpx


@dataclass(frozen=True)
class DataGoKrResponse:
    http_status: int
    result_code: str | None
    result_message: str | None
    authenticated: bool


def normalized_service_key(value: str) -> str:
    """Accept portal Encoding or Decoding keys and return one decoded value.

    The returned value must be passed through httpx/requests ``params`` exactly
    once. It must not be concatenated into a URL or quoted again.
    """
    key = value.strip().strip('"\'')
    if not key:
        raise ValueError("DATA_GO_KR_API_KEY is empty")
    return unquote(key)


def request_with_service_key(
    url: str,
    service_key: str,
    params: dict | None = None,
    *,
    transport: httpx.BaseTransport | None = None,
    timeout: float = 30.0,
) -> httpx.Response:
    query = dict(params or {})
    if "serviceKey" in query:
        raise ValueError("serviceKey must only be supplied by this function")
    query["serviceKey"] = normalized_service_key(service_key)
    with httpx.Client(transport=transport, timeout=timeout, follow_redirects=True) as client:
        return client.get(url, params=query)


def authentication_result(response: httpx.Response) -> DataGoKrResponse:
    code = message = None
    try:
        payload = response.json()
        error = payload.get("OpenAPI_ServiceResponse", {}).get("cmmMsgHeader", {})
        if error:
            code = str(error.get("returnReasonCode")) if error.get("returnReasonCode") is not None else None
            message = error.get("errMsg") or error.get("returnAuthMsg")
        else:
            header = payload.get("response", {}).get("header", {})
            code = str(header.get("resultCode")) if header.get("resultCode") is not None else None
            message = header.get("resultMsg")
    except (ValueError, AttributeError):
        message = "response_format_error"
    authenticated = response.status_code == 200 and code in {None, "00", "0"}
    return DataGoKrResponse(response.status_code, code, message, authenticated)
