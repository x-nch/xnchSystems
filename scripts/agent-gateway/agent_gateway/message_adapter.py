"""Convert OpenAI chat messages to agent prompts."""

from .models import ChatMessage


def messages_to_prompt(messages: list[ChatMessage]) -> tuple[str, str | None]:
    """Return (prompt, system_prompt) from OpenAI-style messages."""
    system_prompt: str | None = None
    parts: list[str] = []

    for message in messages:
        content = _content_to_text(message.content)
        if message.role == "system":
            system_prompt = content
        elif message.role == "user":
            parts.append(f"Human: {content}")
        elif message.role == "assistant":
            parts.append(f"Assistant: {content}")

    prompt = "\n\n".join(parts)
    if messages and messages[-1].role != "user":
        prompt += "\n\nHuman: Please continue."

    return prompt, system_prompt


def _content_to_text(content: str | list[dict[str, object]] | None) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content

    chunks: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text":
            text = block.get("text")
            if isinstance(text, str):
                chunks.append(text)
    return "\n".join(chunks)
