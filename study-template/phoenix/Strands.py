import asyncio
import inspect
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Callable, Awaitable, Union

import httpx
from openai import AsyncOpenAI


TokenProvider = Union[Callable[[], str], Callable[[], Awaitable[str]]]


@dataclass(eq=False)
class StrandsAsyncOpenAI:
    """
    An async OpenAI client wrapper for AWS Strands agents.

    Features:
      - Custom base_url (useful when Strands proxies to OpenAI via AI Gateway)
      - Pluggable httpx.AsyncClient
      - Default and extra headers (merged per request)
      - Rotating auth via token_provider (sync or async callables)
      - Per-request timeout via 'request_timeout'

    Notes:
      - Prefer passing a 'token_provider' that returns a bearer token or API key.
      - If you pass 'api_key', it will be used directly; token_provider overrides it.
      - 'extra_headers' are appended to each request (on top of default_headers).
    """
    # Core config
    base_url: Optional[str] = field(default=None, kw_only=True)
    api_key: Optional[str] = field(default=None, kw_only=True)

    # Networking / headers
    http_client: Optional[httpx.AsyncClient] = field(default=None, repr=False, kw_only=True)
    default_headers: Optional[Dict[str, str]] = field(default=None, repr=False, kw_only=True)
    extra_headers: Optional[Dict[str, str]] = field(default=None, repr=False, kw_only=True)

    # Timeouts
    request_timeout: Optional[float] = field(default=60.0, repr=False, kw_only=True)

    # Rotating token (e.g., AWS AI Gateway-issued bearer)
    token_provider: Optional[TokenProvider] = field(default=None, repr=False, kw_only=True)
    # Optional: header name for the token (defaults to "Authorization: Bearer <token>")
    token_header_name: str = field(default="Authorization", repr=False, kw_only=True)
    token_scheme: str = field(default="Bearer", repr=False, kw_only=True)

    # Internal
    _client: Optional[AsyncOpenAI] = field(default=None, init=False, repr=False)

    def __post_init__(self):
        # Build the underlying SDK client once.
        self._client = self._make_sdk_client()

    def _make_sdk_client(self) -> AsyncOpenAI:
        common: Dict[str, Any] = {}

        if self.base_url:
            common["base_url"] = self.base_url
        if self.default_headers:
            common["default_headers"] = dict(self.default_headers)  # copy
        if self.http_client:
            common["http_client"] = self.http_client

        # If you provide a static api_key and no token_provider, it'll be used.
        # If token_provider is present, we inject auth via headers per call instead.
        if self.api_key and not self.token_provider:
            common["api_key"] = self.api_key

        return AsyncOpenAI(**common)

    def reload_client(self) -> None:
        self._client = self._make_sdk_client()

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            self.reload_client()
        return self._client  # type: ignore[return-value]

    async def _auth_headers(self) -> Dict[str, str]:
        """
        Build auth head
