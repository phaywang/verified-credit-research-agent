"""Small deterministic tool registry for Bedrock tool calling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List


ToolFunction = Callable[..., Any]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: Dict[str, Any]
    function: ToolFunction

    def to_bedrock(self) -> Dict[str, Any]:
        return {
            "toolSpec": {
                "name": self.name,
                "description": self.description,
                "inputSchema": {"json": self.input_schema},
            }
        }


class ToolRegistry:
    def __init__(self, tools: List[ToolSpec]) -> None:
        self._tools = {tool.name: tool for tool in tools}

    @property
    def tools(self) -> List[ToolSpec]:
        return list(self._tools.values())

    def bedrock_config(self) -> Dict[str, Any]:
        return {"tools": [tool.to_bedrock() for tool in self.tools]}

    def invoke(self, name: str, tool_input: Dict[str, Any]) -> Any:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[name].function(**tool_input)
