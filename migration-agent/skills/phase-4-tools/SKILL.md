# Phase 4: Tool Migration & Integration

## Steps
1. Migrate tool definitions to LangGraph ToolNode format
2. Add tool annotations for LangGraph integration
3. Create tool registry with phase-based loading
4. Validate tool execution through pipeline

## Acceptance Criteria
- [ ] All tools accessible through ToolNode
- [ ] Tools registered with correct annotations
- [ ] Pipeline can invoke any tool via selected option
- [ ] Existing tool tests pass with new interface

## Tool Format
```python
from langchain_core.tools import tool

@tool(parse_docstring=True)
def tool_name(param: str) -> str:
    """Docstring used as tool description."""
    return result
```
