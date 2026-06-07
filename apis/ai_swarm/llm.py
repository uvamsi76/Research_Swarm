from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type

from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel


class LLMProvider(ABC):
    @abstractmethod
    def invoke(self, messages: List[Dict[str, str]]) -> Any:
        pass

    @abstractmethod
    def invoke_structured(self, messages: List[Dict[str, str]], output_model: Type[BaseModel]) -> BaseModel:
        pass

    @property
    @abstractmethod
    def model(self) -> Any:
        pass


class LangchainOpenAIProvider(LLMProvider):
    def __init__(
        self,
        model_name: str,
        temperature: float = 0.0,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        max_retries: int = 2,
    ) -> None:
        self._client = ChatOpenAI(
            model=model_name,
            temperature=temperature,
            api_key=api_key or "Empty",
            base_url=base_url,
            max_retries=max_retries,
        )

    def invoke(self, messages: List[Dict[str, str]]) -> Any:
        return self._client.invoke(messages)

    def invoke_structured(self, messages: List[Dict[str, str]], output_model: Type[BaseModel]) -> BaseModel:
        return self._client.with_structured_output(output_model,method="json_schema", strict=True).invoke(messages)

    @property
    def model(self) -> Any:
        return self._client


class LangchainGeminiProvider(LLMProvider):
    def __init__(
        self,
        model_name: str,
        temperature: float = 0.0,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        max_retries: int = 2,
    ) -> None:
        self._client = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=temperature,
            api_key=api_key or "",
            base_url=base_url,
            max_retries=max_retries,
        )

    def invoke(self, messages: List[Dict[str, str]]) -> Any:
        return self._client.invoke(messages)

    def invoke_structured(self, messages: List[Dict[str, str]], output_model: Type[BaseModel]) -> BaseModel:
        return self._client.with_structured_output(output_model,method="json_schema",strict=True).invoke(messages)

    @property
    def model(self) -> Any:
        return self._client


class LLMProviderFactory:
    @staticmethod
    def create(
        provider_name: str,
        model_name: str,
        temperature: float = 0.0,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        max_retries: int = 2,
    ) -> LLMProvider:
        normalized_name = provider_name.strip().lower()

        if normalized_name in {"openai", "langchainopenai", "chatopenai", "aifoundry", "azureaifoundry"}:
            return LangchainOpenAIProvider(
                model_name=model_name,
                temperature=temperature,
                api_key=api_key,
                base_url=base_url,
                max_retries=max_retries,
            )

        if normalized_name in {"gemini", "google", "chatgooglegenerativeai"}:
            return LangchainGeminiProvider(
                model_name=model_name,
                temperature=temperature,
                api_key=api_key,
                base_url=base_url,
                max_retries=max_retries,
            )

        raise ValueError(f"Unsupported LLM provider: {provider_name}")
