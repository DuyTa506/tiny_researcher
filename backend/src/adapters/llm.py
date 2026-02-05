
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import os
import json
import logging

logger = logging.getLogger(__name__)

class LLMClientInterface(ABC):
    @abstractmethod
    async def generate(self, prompt: str, system_instruction: Optional[str] = None, json_mode: bool = False) -> str:
        """Generate text from a prompt."""
        pass

class GeminiAdapter(LLMClientInterface):
    """
    Adapter for Google Gemini API using google-generativeai SDK.
    Requires: pip install google-generativeai
    """
    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash"):
        self.api_key = api_key
        self.model_name = model_name
        self._client = None
        self._model = None
        
    def _ensure_client(self):
        """Lazy initialization of the Gemini client."""
        if self._client is None:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self._client = genai
                self._model = genai.GenerativeModel(self.model_name)
                logger.info(f"Gemini client initialized with model: {self.model_name}")
            except ImportError:
                raise ImportError("google-generativeai package not installed. Run: pip install google-generativeai")
        
    async def generate(self, prompt: str, system_instruction: Optional[str] = None, json_mode: bool = False) -> str:
        self._ensure_client()
        
        try:
            # Build generation config
            generation_config = {}
            if json_mode:
                generation_config["response_mime_type"] = "application/json"
            
            # Combine system instruction with prompt if provided
            full_prompt = prompt
            if system_instruction:
                full_prompt = f"{system_instruction}\n\n{prompt}"
            
            # Generate response (sync call, but we wrap it)
            response = self._model.generate_content(
                full_prompt,
                generation_config=generation_config if generation_config else None
            )
            
            result_text = response.text
            logger.debug(f"Gemini response length: {len(result_text)}")
            return result_text
            
        except Exception as e:
            logger.error(f"Gemini generation error: {e}")
            raise

class OpenAIAdapter(LLMClientInterface):
    """
    Adapter for OpenAI API using openai SDK.
    Requires: pip install openai
    """
    def __init__(self, api_key: str, model_name: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model_name = model_name
        self._client = None
        
    def _ensure_client(self):
        """Lazy initialization of the OpenAI client."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(api_key=self.api_key)
                logger.info(f"OpenAI client initialized with model: {self.model_name}")
            except ImportError:
                raise ImportError("openai package not installed. Run: pip install openai")

    async def generate(self, prompt: str, system_instruction: Optional[str] = None, json_mode: bool = False) -> str:
        self._ensure_client()
        
        try:
            messages = []
            if system_instruction:
                messages.append({"role": "system", "content": system_instruction})
            messages.append({"role": "user", "content": prompt})
            
            kwargs = {
                "model": self.model_name,
                "messages": messages,
            }
            
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            
            response = await self._client.chat.completions.create(**kwargs)
            result_text = response.choices[0].message.content
            logger.debug(f"OpenAI response length: {len(result_text)}")
            return result_text
            
        except Exception as e:
            logger.error(f"OpenAI generation error: {e}")
            raise

class LLMFactory:
    @staticmethod
    def create_client(provider: str = "gemini", **kwargs) -> LLMClientInterface:
        """
        Factory method to create LLM clients.
        
        Args:
            provider: "gemini" or "openai"
            api_key: Optional API key (defaults to env var)
            model_name: Optional model name override
        """
        api_key = kwargs.get("api_key")
        model_name = kwargs.get("model_name")
        
        if provider == "gemini":
            key = api_key or os.getenv("GEMINI_API_KEY")
            if not key:
                raise ValueError("GEMINI_API_KEY not set")
            return GeminiAdapter(
                api_key=key, 
                model_name=model_name or "gemini-2.0-flash"
            )
        elif provider == "openai":
            key = api_key or os.getenv("OPENAI_API_KEY")
            if not key:
                raise ValueError("OPENAI_API_KEY not set")
            return OpenAIAdapter(
                api_key=key,
                model_name=model_name or "gpt-5-nano"
            )
        else:
            raise ValueError(f"Unknown LLM provider: {provider}")
