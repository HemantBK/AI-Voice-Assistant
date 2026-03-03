import logging
from groq import Groq
from app.config import GROQ_API_KEY, LLM_MODEL, SYSTEM_PROMPT

logger = logging.getLogger(__name__)

_client = None


def get_client():
    global _client
    if _client is None:
        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is not set. Get a free key at https://console.groq.com")
        _client = Groq(api_key=GROQ_API_KEY)
    return _client


def chat(user_message: str, conversation_history: list[dict] | None = None) -> str:
    """Send a message to the LLM and get a response."""
    client = get_client()

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if conversation_history:
        messages.extend(conversation_history)

    messages.append({"role": "user", "content": user_message})

    logger.info(f"Sending to Groq ({LLM_MODEL}): {user_message[:100]}...")

    completion = client.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        temperature=0.7,
        max_tokens=256,
    )

    response = completion.choices[0].message.content
    logger.info(f"Groq response: {response[:100]}...")
    return response


def chat_stream(user_message: str, conversation_history: list[dict] | None = None):
    """Stream a response from the LLM, yielding chunks."""
    client = get_client()

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if conversation_history:
        messages.extend(conversation_history)

    messages.append({"role": "user", "content": user_message})

    stream = client.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        temperature=0.7,
        max_tokens=256,
        stream=True,
    )

    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
