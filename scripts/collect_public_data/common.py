from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VALID_STATUSES = {
    "collected", "processed", "integrated", "blocked_auth", "blocked_access",
    "source_unavailable", "insufficient_fields", "pending_verification",
}


@dataclass
class CollectionResult:
    dataset: str
    source_url: str
    status: str
    fetched_at: str
    raw_path: str | None = None
    row_count: int = 0
    note: str = ""
    sha256: str | None = None

    def __post_init__(self) -> None:
        if self.status not in VALID_STATUSES:
            raise ValueError(f"unsupported collection status: {self.status}")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def fetch(url: str, destination: Path, *, timeout: int = 30) -> CollectionResult:
    """Fetch once, atomically replace, and retain a checksum. Existing good raw data survives failure."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "shh-schedule-poc/0.2 public-data-research"})
    try:
        context = None
        try:
            import certifi
            import ssl
            context = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            pass
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            body = response.read()
        tmp = destination.with_suffix(destination.suffix + ".tmp")
        tmp.write_bytes(body)
        tmp.replace(destination)
        return CollectionResult(destination.parent.name, url, "collected", utc_now(), str(destination), sha256=hashlib.sha256(body).hexdigest())
    except urllib.error.HTTPError as exc:
        status = "blocked_auth" if exc.code in {401, 403} else "source_unavailable"
        return CollectionResult(destination.parent.name, url, status, utc_now(), note=f"HTTP {exc.code}")
    except (urllib.error.URLError, TimeoutError) as exc:
        return CollectionResult(destination.parent.name, url, "blocked_access", utc_now(), note=str(exc.reason if hasattr(exc, "reason") else exc))


def blocked_auth(dataset: str, url: str, env_name: str) -> CollectionResult:
    return CollectionResult(dataset, url, "blocked_auth", utc_now(), note=f"Set {env_name} in the environment; no key is stored in the repository.")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def result_dict(result: CollectionResult) -> dict[str, Any]:
    return asdict(result)


def env(name: str) -> str | None:
    return os.environ.get(name) or None
