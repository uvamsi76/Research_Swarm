import logging
import os

from dotenv import load_dotenv

from .llm import LLMProviderFactory, LLMProvider

load_dotenv()
logger = logging.getLogger(__name__)


def build_llm_provider_from_env() -> LLMProvider:
    provider_name = os.getenv("LLM_PROVIDER", "openai")
    model_name = os.getenv("LLM_MODEL", "google/gemma-4-E2B-it")
    temperature = float(os.getenv("LLM_TEMPERATURE", "1.0"))
    api_key = os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_BASE_URL")
    max_retries = int(os.getenv("LLM_MAX_RETRIES", "2"))

    try:
        return LLMProviderFactory.create(
            provider_name=provider_name,
            model_name=model_name,
            temperature=temperature,
            api_key=api_key,
            base_url=base_url,
            max_retries=max_retries,
        )
    except ValueError as exc:
        logger.exception("Invalid LLM provider configuration")
        raise
