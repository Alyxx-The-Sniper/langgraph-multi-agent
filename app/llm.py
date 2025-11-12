# app/llm.py
from langchain_community.chat_models import ChatDeepInfra
from .config import settings

# Initialize your LLM here, pulling the key from config
llm = ChatDeepInfra(
    api_key=settings.DEEPINFRA_API_KEY,
    model='openai/gpt-oss-120b',
    temperature=0,
    max_tokens=2048,
    model_kwargs={"tool_choice": "auto"}
)

print("✅ LLM (DeepInfra) initialized.")