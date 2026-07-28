"""Validate pipeline migration — compare old vs new pipeline outputs."""
import asyncio
from uuid import uuid4


async def validate():
    test_inputs = [
        "list all services",
        "deploy the staging environment",
        "analyze database performance",
        "escalate to human operator",
    ]

    from nexi.pipeline.intent_interpreter import IntentInterpreter
    from xnch.agents.pipeline_graph import create_pipeline

    old_interpreter = IntentInterpreter()
    new_pipeline = create_pipeline()

    for raw_input in test_inputs:
        session_id = str(uuid4())
        trace_id = str(uuid4())

        old_intent = await old_interpreter.interpret(
            raw_input, uuid4(session_id), trace_id
        )

        result = new_pipeline.invoke(
            {
                "raw_input": raw_input,
                "session_id": session_id,
                "trace_id": trace_id,
            }
        )
        new_intent = result.get("intent", {})

        match = old_intent.intent_class == new_intent.get("intent_class")
        status = "PASS" if match else "FAIL"
        print(
            f"[{status}] '{raw_input}': "
            f"old={old_intent.intent_class}, new={new_intent.get('intent_class')}"
        )


if __name__ == "__main__":
    asyncio.run(validate())
