"""Message adapter tests."""

from agent_gateway.message_adapter import messages_to_prompt
from agent_gateway.models import ChatMessage


def test_messages_to_prompt_extracts_system_and_user() -> None:
    prompt, system = messages_to_prompt(
        [
            ChatMessage(role="system", content="Be concise."),
            ChatMessage(role="user", content="Hello"),
        ]
    )
    assert system == "Be concise."
    assert prompt == "Human: Hello"
