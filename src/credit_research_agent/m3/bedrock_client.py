"""Bedrock Converse client and multi-turn tool loop for M3 Phase 1."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from credit_research_agent.m3.tool_registry import ToolRegistry


DEFAULT_MODEL_ID = "us.anthropic.claude-sonnet-4-6"
_CROSS_REGION_PREFIXES = ("us", "eu", "ap")


@dataclass
class ToolLoopEvent:
    kind: str
    reasoning_summary: str
    decision_basis: List[str] = field(default_factory=list)
    tool_name: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    tool_result: Optional[Any] = None
    text: Optional[str] = None


@dataclass
class ToolLoopResult:
    final_text: str
    events: List[ToolLoopEvent]
    messages: List[Dict[str, Any]]
    stop_reason: str


@dataclass
class TextInvokeResult:
    text: str
    messages: List[Dict[str, Any]]
    stop_reason: str


def load_project_env(path: Optional[Path] = None) -> None:
    """Load Bedrock env settings using the financial-dd-agent pattern."""

    try:
        from dotenv import load_dotenv
    except ImportError:
        _load_env_without_dependency(path or _default_env_path())
        return

    env_path = path or _default_env_path()
    if env_path.exists():
        load_dotenv(env_path, override=False)


def _default_env_path() -> Path:
    return Path(".env")


def _load_env_without_dependency(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def provider_from_model_id(model_id: str) -> Optional[str]:
    """Extract provider from Bedrock model ID, matching financial-dd-agent."""

    if model_id.startswith("arn:"):
        try:
            return model_id.split("/")[-1].split(".")[0]
        except Exception:
            return None
    parts = model_id.split(".")
    if len(parts) >= 2:
        return parts[1] if parts[0] in _CROSS_REGION_PREFIXES else parts[0]
    return None


def resolve_aws_params(
    profile: Optional[str] = None,
    region: Optional[str] = None,
    model_id: Optional[str] = None,
) -> tuple[Optional[str], str, str, Optional[str]]:
    """Resolve AWS params using financial-dd-agent env names."""

    load_project_env()
    resolved_profile = (profile or os.getenv("AWS_PROFILE", "")).strip() or None
    resolved_region = (
        (region or os.getenv("AWS_REGION", "")).strip()
        or os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    )
    resolved_model = model_id or os.getenv("BEDROCK_MODEL_ID", DEFAULT_MODEL_ID)
    provider = (
        os.getenv("BEDROCK_MODEL_PROVIDER", "").strip().lower()
        or provider_from_model_id(resolved_model)
    )
    return resolved_profile, resolved_region, resolved_model, provider


def build_bedrock_runtime_client() -> Any:
    try:
        import boto3
    except ImportError as exc:
        raise RuntimeError("boto3 is required for Bedrock Phase 1 gate.") from exc

    profile, region, _, _ = resolve_aws_params()
    session = boto3.Session(profile_name=profile, region_name=region)
    return session.client("bedrock-runtime")


def invoke_with_tools(
    prompt: str,
    registry: ToolRegistry,
    *,
    system_prompt: str = "You are a careful tool-using assistant.",
    model_id: Optional[str] = None,
    max_turns: int = 8,
    max_tokens: int = 1024,
    client: Any = None,
) -> ToolLoopResult:
    """Invoke Bedrock Claude with tools until final text or max_turns."""

    runtime = client or build_bedrock_runtime_client()
    _, _, resolved_model, _ = resolve_aws_params(model_id=model_id)
    messages: List[Dict[str, Any]] = [
        {"role": "user", "content": [{"text": prompt}]}
    ]
    events: List[ToolLoopEvent] = []
    final_text = ""
    stop_reason = ""

    for turn in range(max_turns):
        response = runtime.converse(
            modelId=resolved_model,
            system=[{"text": system_prompt}],
            messages=messages,
            toolConfig=registry.bedrock_config(),
            inferenceConfig={"temperature": 0, "maxTokens": max_tokens},
        )
        output_message = response["output"]["message"]
        stop_reason = response.get("stopReason", "")
        messages.append(output_message)

        content = output_message.get("content", [])
        text_parts = [block["text"] for block in content if "text" in block]
        if text_parts:
            final_text = "\n".join(text_parts)
            events.append(
                ToolLoopEvent(
                    kind="assistant_text",
                    reasoning_summary=f"Assistant returned text on turn {turn + 1}.",
                    text=final_text,
                )
            )

        tool_uses = [block["toolUse"] for block in content if "toolUse" in block]
        if not tool_uses:
            return ToolLoopResult(
                final_text=final_text,
                events=events,
                messages=messages,
                stop_reason=stop_reason,
            )

        tool_result_blocks = []
        for tool_use in tool_uses:
            tool_name = tool_use["name"]
            tool_input = tool_use.get("input", {})
            result = registry.invoke(tool_name, tool_input)
            events.append(
                ToolLoopEvent(
                    kind="tool_call",
                    reasoning_summary=f"Claude requested deterministic tool `{tool_name}`.",
                    decision_basis=[
                        f"toolUseId={tool_use['toolUseId']}",
                        f"input={json.dumps(tool_input, sort_keys=True)}",
                    ],
                    tool_name=tool_name,
                    tool_input=tool_input,
                    tool_result=result,
                )
            )
            tool_result_blocks.append(
                {
                    "toolResult": {
                        "toolUseId": tool_use["toolUseId"],
                        "content": [{"json": _jsonable(result)}],
                    }
                }
            )

        messages.append({"role": "user", "content": tool_result_blocks})

    return ToolLoopResult(
        final_text=final_text,
        events=events,
        messages=messages,
        stop_reason=stop_reason or "max_turns",
    )


def invoke_text(
    prompt: str,
    *,
    system_prompt: str = "You are a careful credit research assistant.",
    model_id: Optional[str] = None,
    max_tokens: int = 2048,
    client: Any = None,
) -> TextInvokeResult:
    """Invoke Bedrock Claude without exposing deterministic tools."""

    runtime = client or build_bedrock_runtime_client()
    _, _, resolved_model, _ = resolve_aws_params(model_id=model_id)
    messages: List[Dict[str, Any]] = [
        {"role": "user", "content": [{"text": prompt}]}
    ]
    response = runtime.converse(
        modelId=resolved_model,
        system=[{"text": system_prompt}],
        messages=messages,
        inferenceConfig={"temperature": 0, "maxTokens": max_tokens},
    )
    output_message = response["output"]["message"]
    messages.append(output_message)
    text = "\n".join(
        block["text"] for block in output_message.get("content", []) if "text" in block
    )
    return TextInvokeResult(
        text=text,
        messages=messages,
        stop_reason=response.get("stopReason", ""),
    )


def _jsonable(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        return json.loads(json.dumps(value, default=str))
