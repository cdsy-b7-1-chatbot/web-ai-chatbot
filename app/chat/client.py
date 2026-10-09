"""OpenRouter 호출 경계 — 제공자 설정·응답 해석을 채팅 로직에서 분리한다."""

from dataclasses import dataclass
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.chat.context import Message
from app.core.config import Settings, get_settings

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
PROVIDER = "streamlake"


class AIClientError(Exception):
    def __init__(self, code: Literal["AI_ERROR", "AI_TIMEOUT", "AI_NOT_CONFIGURED"]) -> None:
        # 외부 오류 원문을 보관하지 않아 상위 로그에도 키·본문이 섞이지 않게 한다.
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class AIResult:
    answer: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    truncated: bool


class _Message(BaseModel):
    content: str


class _Choice(BaseModel):
    message: _Message
    finish_reason: str | None = None


class _Usage(BaseModel):
    prompt_tokens: int | None = Field(default=None, ge=0, strict=True)
    completion_tokens: int | None = Field(default=None, ge=0, strict=True)


class _Completion(BaseModel):
    model_config = ConfigDict(extra="ignore")

    choices: list[_Choice] = Field(min_length=1)
    model: str | None = None
    usage: _Usage | None = None
    error: object | None = None


class OpenRouterClient:
    def __init__(
        self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self.settings = settings
        self.transport = transport

    def ensure_configured(self) -> None:
        key = self.settings.openrouter_api_key
        if key is None or not key.get_secret_value().strip():
            raise AIClientError("AI_NOT_CONFIGURED")

    def _headers(self) -> dict[str, str]:
        self.ensure_configured()
        headers = {
            "Authorization": f"Bearer {self.settings.openrouter_api_key.get_secret_value().strip()}",
            "Content-Type": "application/json",
        }
        for name, value in (
            ("HTTP-Referer", self.settings.openrouter_site_url),
            ("X-OpenRouter-Title", self.settings.openrouter_site_name),
        ):
            if value and value.strip():
                headers[name] = value.strip()
        return headers

    async def generate(self, messages: list[Message]) -> AIResult:
        payload = {
            "model": self.settings.ai_model,
            "messages": messages,
            "stream": False,
            "max_tokens": self.settings.ai_max_output_tokens,
            # 요청마다 명시해 OpenRouter의 기본 제공자 fallback을 차단한다.
            "provider": {"only": [PROVIDER], "allow_fallbacks": False},
        }
        async with httpx.AsyncClient(
            timeout=self.settings.ai_timeout_seconds, transport=self.transport
        ) as http:
            response = await http.post(OPENROUTER_URL, headers=self._headers(), json=payload)
            response.raise_for_status()
        try:
            completion = _Completion.model_validate(response.json())
        except (ValueError, ValidationError):
            raise AIClientError("AI_ERROR") from None
        choice = completion.choices[0]
        if completion.error is not None or choice.finish_reason in {"error", "content_filter"}:
            raise AIClientError("AI_ERROR")
        answer = choice.message.content.strip()
        if not answer:
            raise AIClientError("AI_ERROR")
        usage = completion.usage
        return AIResult(
            answer=answer,
            model=completion.model or self.settings.ai_model,
            input_tokens=usage.prompt_tokens if usage else None,
            output_tokens=usage.completion_tokens if usage else None,
            truncated=choice.finish_reason == "length",
        )


def get_ai_client() -> OpenRouterClient:
    return OpenRouterClient(get_settings())
