"""XNCH/Nexi Migration Agent — orchestrates migration to LangGraph + Deep Agents + Memgraph."""

import os
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI

from tools.graph_migration import (
    create_memgraph_schema,
    migrate_entities_to_memgraph,
    migrate_relations_to_memgraph,
    validate_graph_migration,
)
from tools.memory_migration import (
    create_composite_backend,
    migrate_episodic_to_store,
    migrate_patterns_to_store,
    validate_memory_migration,
)
from tools.pipeline_migration import (
    define_decision_state,
    create_langgraph_pipeline,
    add_human_in_the_loop,
    validate_pipeline_migration,
)
from tools.infrastructure import (
    deploy_memgraph,
    setup_postgres_checkpointer,
    add_dependencies,
    verify_infrastructure,
)

from langgraph.checkpoint.memory import MemorySaver

LOCAL_LLM_BASE_URL = os.environ.get("LOCAL_LLM_BASE_URL", "http://192.168.1.9:8082/v1")
LOCAL_LLM_MODEL = os.environ.get("LOCAL_LLM_MODEL", "ornith-1.0-35b")

model = ChatOpenAI(
    model=LOCAL_LLM_MODEL,
    base_url=LOCAL_LLM_BASE_URL,
    api_key="none",
    temperature=0,
    max_tokens=4096,
)

instructions_path = os.path.join(os.path.dirname(__file__), "instructions.md")
system_prompt = open(instructions_path).read() if os.path.exists(instructions_path) else None

agent = create_agent(
    model=model,
    tools=[
        # Phase 0: Infrastructure
        deploy_memgraph,
        setup_postgres_checkpointer,
        add_dependencies,
        verify_infrastructure,
        # Phase 1: Graph Migration
        create_memgraph_schema,
        migrate_entities_to_memgraph,
        migrate_relations_to_memgraph,
        validate_graph_migration,
        # Phase 2: Memory Migration
        create_composite_backend,
        migrate_episodic_to_store,
        migrate_patterns_to_store,
        validate_memory_migration,
        # Phase 3: Pipeline Migration
        define_decision_state,
        create_langgraph_pipeline,
        add_human_in_the_loop,
        validate_pipeline_migration,
    ],
    system_prompt=system_prompt,
    interrupt_before=["tools"],
    checkpointer=MemorySaver(),
)

if __name__ == "__main__":
    import sys
    from langgraph.types import Command

    prompt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Begin Phase 0: Deploy Memgraph and set up infrastructure."
    thread_config = {"configurable": {"thread_id": "migration-cli"}}

    print(f"Running migration agent: {prompt}\n")
    result = agent.invoke(
        {"messages": [{"role": "user", "content": prompt}]},
        config=thread_config,
    )

    # Print results and handle interrupts
    while True:
        for msg in result.get("messages", []):
            if hasattr(msg, "content") and msg.content:
                print(f"\n[{msg.type}] {msg.content[:1500]}")
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    print(f"\n  -> {tc['name']}({tc['args']})")

        # Check if we hit an interrupt
        state = agent.get_state(thread_config)
        if state.next:
            print(f"\n--- Paused before: {state.next} ---")
            answer = input("Approve? (y/n/edit): ").strip().lower()
            if answer == "y":
                result = agent.invoke(Command(resume=True), config=thread_config)
            elif answer == "n":
                result = agent.invoke(Command(resume=False), config=thread_config)
            elif answer == "edit":
                edit_msg = input("Enter edited response: ")
                result = agent.invoke(Command(resume={"approved": True, "edited_response": edit_msg}), config=thread_config)
            else:
                print("Invalid input. Resuming with approval.")
                result = agent.invoke(Command(resume=True), config=thread_config)
        else:
            break

    print("\n--- Migration agent complete ---")
