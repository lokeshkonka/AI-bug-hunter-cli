import json
from typing import Optional, Dict, Any, Type
from pydantic import BaseModel
from bughunter.agents.prompt_guard.prompt_guard_agent import PromptGuardAgent
from bughunter.storage.provider_store import ProviderStore
from bughunter.config_manager import ConfigManager

class ProviderAdapter:
    def __init__(self, run_id: str, db_path: str):
        self.run_id = run_id
        self.prompt_guard = PromptGuardAgent(run_id, db_path)
        self.provider_store = ProviderStore(db_path)
        self.config = ConfigManager.load()
        self.profile = ConfigManager.get_active_profile()

    @property
    def llm(self):
        if not self.profile:
            raise ValueError("No active profile")
        model_name = self.profile.model
        provider = self.profile.provider.lower()
        api_key = self.profile.api_key
        
        if provider == "groq":
            from langchain_groq import ChatGroq
            return ChatGroq(model=model_name, api_key=api_key)
        elif provider == "openai" or provider == "grok":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=model_name, 
                api_key=api_key,
                base_url="https://api.x.ai/v1" if provider == "grok" else None
            )
        elif provider == "gemini":
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(model=model_name, google_api_key=api_key)
        else:
            raise ValueError(f"Unsupported provider: {provider}")
        
    async def send_with_guard(self, agent: str, system_prompt: str, untrusted_content: str, response_schema: Type[BaseModel]) -> BaseModel:
        # Wrap the untrusted content using PromptGuardAgent
        wrapped_content = await self.prompt_guard.scan_and_wrap(untrusted_content)
        
        full_prompt = f"{system_prompt}\n\nEvidence:\n{wrapped_content}"
        
        # Determine model
        if not self.profile:
            raise ValueError("No active profile")
            
        model_name = self.profile.model
        provider = self.profile.provider.lower()
        api_key = self.profile.api_key
        
        result = None
        prompt_tokens = 0
        completion_tokens = 0
        
        if provider == "groq":
            from langchain_groq import ChatGroq
            llm = ChatGroq(model=model_name, api_key=api_key)
            structured_llm = llm.with_structured_output(response_schema)
            result = structured_llm.invoke(full_prompt)
            
            import tiktoken
            encoder = tiktoken.get_encoding("cl100k_base")
            prompt_tokens = len(encoder.encode(full_prompt))
            completion_tokens = len(encoder.encode(str(result)))

        elif provider == "openai" or provider == "grok":
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(
                model=model_name, 
                api_key=api_key,
                base_url="https://api.x.ai/v1" if provider == "grok" else None
            )
            structured_llm = llm.with_structured_output(response_schema)
            # Invoke
            result = structured_llm.invoke(full_prompt)
            
            # OpenAI doesn't natively expose token counts through with_structured_output easily without callbacks in some versions
            # We'll use a rough estimation
            import tiktoken
            encoder = tiktoken.get_encoding("cl100k_base")
            prompt_tokens = len(encoder.encode(full_prompt))
            completion_tokens = len(encoder.encode(str(result)))
            
        elif provider == "gemini":
            from langchain_google_genai import ChatGoogleGenerativeAI
            llm = ChatGoogleGenerativeAI(model=model_name, google_api_key=api_key)
            structured_llm = llm.with_structured_output(response_schema)
            result = structured_llm.invoke(full_prompt)
            
            import tiktoken
            encoder = tiktoken.get_encoding("cl100k_base")
            prompt_tokens = len(encoder.encode(full_prompt))
            completion_tokens = len(encoder.encode(str(result)))
            
        else:
            raise ValueError(f"Unsupported provider: {provider}")
            
        # Log usage
        # Actual cost calculation based on model
        pricing = {
            "gpt-4o": {"prompt": 0.000005, "completion": 0.000015},
            "gpt-4o-mini": {"prompt": 0.00000015, "completion": 0.0000006},
            "claude-3-5-sonnet-20240620": {"prompt": 0.000003, "completion": 0.000015},
            "gemini-1.5-pro": {"prompt": 0.0000035, "completion": 0.0000105},
            "gemini-1.5-flash": {"prompt": 0.000000075, "completion": 0.0000003},
        }
        rates = pricing.get(model_name.lower(), {"prompt": 0.000001, "completion": 0.000002})
        cost = (prompt_tokens * rates["prompt"]) + (completion_tokens * rates["completion"])
        await self.provider_store.log_usage(
            run_id=self.run_id,
            agent=agent,
            test_id=None,
            model=model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            estimated_cost_usd=cost
        )
        
        return result
