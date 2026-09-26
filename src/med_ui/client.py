"""The UI's only route to scoring: HTTP calls to the Phase 6 API.

`GET /ready`, `POST /assess`, and `POST /feedback`. Nothing here scores,
applies a cutoff, or reads the model. A transport failure is returned as a
response with no status code, which the presentation layer shows as
unable to assess.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from med_ui.config import (
    CONNECT_TIMEOUT_SECONDS,
    FEEDBACK_LABELS,
    READ_TIMEOUT_SECONDS,
    REQUEST_FIELDS,
    UiSettings,
)


@dataclass(frozen=True)
class ApiResponse:
    status_code: int | None
    body: dict | None
    error: str | None = None

    @property
    def reached(self) -> bool:
        return self.status_code is not None


class ApiClient:
    def __init__(self, base_url: str | None = None, *, http: httpx.Client | None = None):
        if http is None:
            if base_url is None:
                raise ValueError("ApiClient needs a base URL or an HTTP client")
            timeout = httpx.Timeout(READ_TIMEOUT_SECONDS, connect=CONNECT_TIMEOUT_SECONDS)
            http = httpx.Client(base_url=base_url, timeout=timeout)
        self._http = http

    def ready(self) -> ApiResponse:
        return self._call("GET", "/ready")

    def assess(self, request: dict) -> ApiResponse:
        extra = set(request) - set(REQUEST_FIELDS)
        if extra:
            raise ValueError(f"The UI sends only the Phase 1 request fields, not {sorted(extra)}")
        return self._call("POST", "/assess", json=request)

    def feedback(self, request_id: str, recipient: str, label: str) -> ApiResponse:
        if label not in FEEDBACK_LABELS:
            raise ValueError(f"label must be one of {FEEDBACK_LABELS}")
        return self._call("POST", "/feedback", json={"request_id": request_id, "recipient": recipient, "label": label})

    def _call(self, method: str, path: str, **kwargs) -> ApiResponse:
        try:
            response = self._http.request(method, path, **kwargs)
        except httpx.HTTPError as error:
            return ApiResponse(status_code=None, body=None, error=f"{type(error).__name__}: {error}")
        try:
            body = response.json()
        except ValueError:
            body = None
        if not isinstance(body, dict):
            body = None
        return ApiResponse(status_code=response.status_code, body=body)


def make_client(settings: UiSettings) -> ApiClient:
    return ApiClient(settings.api_url)
