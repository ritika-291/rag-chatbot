import os
from langchain_openai import ChatOpenAI


def get_llm():
    # Allow configurable request timeout (seconds)
    try:
        request_timeout = int(os.getenv("LLM_REQUEST_TIMEOUT", "60"))
    except Exception:
        request_timeout = 60

    return ChatOpenAI(
        model=os.getenv("LLM_MODEL_NAME"),
        api_key=os.getenv("LLM_API_KEY"),
        base_url=os.getenv("LLM_URL"),
        temperature=0,
        request_timeout=request_timeout,
    )