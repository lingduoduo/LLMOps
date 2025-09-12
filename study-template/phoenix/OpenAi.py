import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Callable

from openai import OpenAI, AzureOpenAI
from phoenix.evals.models.openai import OpenAIModel as PhoenixOpenAIModel

@dataclass(eq=False)
class OpenAIModel(PhoenixOpenAIModel):
    """
    Extends Phoenix's OpenAIModel to support custom http_client, headers,
    and *rotating* Azure AD tokens via azure_ad_token_provider.
    """
    http_client: Optional[Any] = field(default=None, repr=False, kw_only=True)
    default_headers: Optional[Dict[str, str]] = field(default=None, repr=False, kw_only=True)
    extra_headers: Optional[Dict[str, str]] = field(default=None, repr=False, kw_only=True)

    # Phoenix uses 'request_timeout' (not 'timeout'); keep this name for consistency
    request_timeout: Optional[float] = field(default=60, repr=False, kw_only=True)

    # Azure auth: pass a provider so the SDK fetches a fresh token per request
    azure_ad_token_provider: Optional[Callable[[], str]] = field(default=None, repr=False, kw_only=True)

    def __post_init__(self):
        super().__post_init__()
        # Force client creation with our custom settings
        self._client = self._make_sdk_client()

    def _make_sdk_client(self):
        # Common kwargs for both OpenAI and AzureOpenAI
        common: Dict[str, Any] = {}

        if getattr(self, "base_url", None) is not None:
            common["base_url"] = self.base_url
        if self.default_headers is not None:
            common["default_headers"] = self.default_headers
        if self.http_client is not None:
            common["http_client"] = self.http_client

        # IMPORTANT:
        # 1) Do not pass a static api_key if you use azure_ad_token_provider.
        # 2) Let the SDK call your provider for a fresh token on each request.
        if getattr(self, "azure_endpoint", None):
            return AzureOpenAI(
                api_version=getattr(self, "api_version", None),
                azure_endpoint=self.azure_endpoint,
                # Do NOT pass azure_ad_token or api_key if you supply the provider.
                azure_ad_token_provider=self.azure_ad_token_provider,
                **common,
            )

        # (If you ever use public OpenAI instead of Azure)
        if getattr(self, "api_key", None) is not None:
            common["api_key"] = self.api_key
        return OpenAI(**common)

    def reload_client(self) -> None:
        self._client = self._make_sdk_client()

    @property
    def invocation_params(self) -> Dict[str, Any]:
        # Phoenix will pass 'model' on calls; we can add per-request headers here.
        params = dict(super().invocation_params)
        if self.extra_headers:
            params["extra_headers"] = self.extra_headers
        # Respect Phoenix’s request_timeout field
        if self.request_timeout is not None:
            params["timeout"] = self.request_timeout
        # # Override temperature to 1 (only supported value for this model)
        params["temperature"] = 1
        return params
