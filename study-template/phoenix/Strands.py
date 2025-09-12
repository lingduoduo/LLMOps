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
        Build auth headers:
          - If token_provider is set, call it (await if needed) and format as:
              { token_header_name: "{token_scheme} {token}" }
          - Else, return empty (the SDK will use api_key if provided).
        """
        if not self.token_provider:
            return {}

        token_or_coro = self.token_provider()
        token = await token_or_coro if inspect.isawaitable(token_or_coro) else token_or_coro
        return {self.token_header_name: f"{self.token_scheme} {token}" if self.token_scheme else token}

    @property
    def invocation_params(self) -> Dict[str, Any]:
        """
        Default invocation params to merge into each model call.
        You can add defaults here (e.g., temperature) per your policy.
        """
        params: Dict[str, Any] = {}
        if self.request_timeout is not None:
            params["timeout"] = self.request_timeout
        # Example: enforce deterministic generation policy
        # params["temperature"] = 0
        return params

    async def chat(self, *, model: str, messages: list, **kwargs) -> Any:
        """
        Convenience method for chat completions with merged headers/timeouts.
        Example use inside Strands: await wrapper.chat(model="gpt-4o-mini", messages=[...])
        """
        # Merge invocation defaults
        call_kwargs = dict(self.invocation_params)
        call_kwargs.update(kwargs or {})

        # Merge headers: default (SDK) + our per-call extra_headers + dynamic auth
        extra_headers = dict(self.extra_headers or {})
        extra_headers.update(await self._auth_headers())
        if extra_headers:
            call_kwargs["extra_headers"] = extra_headers

        return await self.client.chat.completions.create(
            model=model,
            messages=messages,
            **call_kwargs,
        )

    async def responses(self, *, model: str, input: Any, **kwargs) -> Any:
        """
        Convenience method for the newer Responses API (if you use it).
        """
        call_kwargs = dict(self.invocation_params)
        call_kwargs.update(kwargs or {})

        extra_headers = dict(self.extra_headers or {})
        extra_headers.update(await self._auth_headers())
        if extra_headers:
            call_kwargs["extra_headers"] = extra_headers

        # If you prefer Responses API:
        return await self.client.responses.create(
            model=model,
            input=input,
            **call_kwargs,
        )


# Suppose Strands gives you:
#   - A proxy base URL (AI Gateway)
#   - A short-lived bearer token provider

async def get_gateway_token() -> str:
    # Your logic here (e.g., call STS / OIDC / internal endpoint)
    return "eyJhbGciOi..."  # example JWT

wrapper = StrandsAsyncOpenAI(
    base_url="https://your-aigw.example.com/v1",   # or whatever Strands proxy uses
    token_provider=get_gateway_token,              # rotates per call
    default_headers={"x-tenant-id": "my-tenant"},
    extra_headers={"x-trace-id": "abc-123"},
    request_timeout=45.0,
)

async def run():
    resp = await wrapper.chat(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Hello from Strands!"}],
    )
    print(resp.choices[0].message.content)

asyncio.run(run())
