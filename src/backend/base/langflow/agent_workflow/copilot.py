"""Copilot Agent for automatic workflow generation."""

from __future__ import annotations

import json
import secrets
from pathlib import Path
from typing import Any

from lfx.log.logger import logger

from langflow.services.deps import get_settings_service


def load_system_prompt() -> str:
    """Load the system prompt from markdown file."""
    prompt_path = Path(__file__).parent / "system_prompt1.md"
    with prompt_path.open("r", encoding="utf-8") as f:
        return f.read()


def generate_node_id(prefix: str) -> str:
    """Generate a unique node ID."""
    random_suffix = secrets.token_hex(3)
    return f"{prefix}-{random_suffix}"


def validate_workflow_json(workflow_data: dict[str, Any]) -> tuple[bool, str | None]:
    """Validate the generated workflow JSON structure.

    Args:
        workflow_data: The workflow JSON data to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        # 先检查是否有 "data" 字段
        if "data" in workflow_data:
            workflow_data = workflow_data["data"]

        # Check required top-level fields
        if "nodes" not in workflow_data:
            return False, "Missing 'nodes' field"
        if "edges" not in workflow_data:
            return False, "Missing 'edges' field"

        nodes = workflow_data.get("nodes", [])
        edges = workflow_data.get("edges", [])

        if not isinstance(nodes, list):
            return False, "'nodes' must be a list"
        if not isinstance(edges, list):
            return False, "'edges' must be a list"

        if len(nodes) == 0:
            return False, "Workflow must contain at least one node"

        # Validate nodes structure
        node_ids = set()
        for i, node in enumerate(nodes):
            if not isinstance(node, dict):
                return False, f"Node {i} must be a dictionary"

            if "id" not in node:
                return False, f"Node {i} missing 'id' field"
            node_id = node["id"]
            if node_id in node_ids:
                return False, f"Duplicate node ID: {node_id}"
            node_ids.add(node_id)

            if "data" not in node:
                return False, f"Node {i} missing 'data' field"

            node_data = node["data"]
            if not isinstance(node_data, dict):
                return False, f"Node {i} 'data' must be a dictionary"

            # Check for required node data fields
            if "id" not in node_data:
                return False, f"Node {i} data missing 'id' field"
            if "node" not in node_data:
                return False, f"Node {i} data missing 'node' field"

            node_inner = node_data.get("node", {})
            if "template" not in node_inner:
                return False, f"Node {i} missing 'template' field"

        # Validate edges structure
        for i, edge in enumerate(edges):
            if not isinstance(edge, dict):
                return False, f"Edge {i} must be a dictionary"

            if "source" not in edge:
                return False, f"Edge {i} missing 'source' field"
            if "target" not in edge:
                return False, f"Edge {i} missing 'target' field"

            source_id = edge["source"]
            target_id = edge["target"]

            if source_id not in node_ids:
                return False, f"Edge {i} references non-existent source node: {source_id}"
            if target_id not in node_ids:
                return False, f"Edge {i} references non-existent target node: {target_id}"

        return True, None

    except Exception as e:
        return False, f"Validation error: {e!s}"


def format_workflow_json(workflow_data: dict[str, Any]) -> dict[str, Any]:
    """Format and normalize the workflow JSON to match Langflow format.

    Args:
        workflow_data: The raw workflow JSON data

    Returns:
        Formatted workflow JSON with proper structure
    """
    # Ensure viewport exists
    if "viewport" not in workflow_data:
        workflow_data["viewport"] = {"x": 0, "y": 0, "zoom": 1}

    # Ensure nodes have proper structure
    nodes = workflow_data.get("nodes", [])
    for node in nodes:
        # Ensure position exists
        if "position" not in node:
            node["position"] = {"x": 0, "y": 0}

        # Ensure type exists
        if "type" not in node:
            node["type"] = "genericNode"

        # Ensure width and height
        if "width" not in node:
            node["width"] = 320
        if "height" not in node:
            node["height"] = 234

        # Ensure data structure
        if "data" in node and isinstance(node["data"], dict):
            node_data = node["data"]
            if "type" not in node_data:
                # Try to infer from node id
                node_id = node.get("id", "")
                if "ChatInput" in node_id:
                    node_data["type"] = "ChatInput"
                elif "Prompt" in node_id:
                    node_data["type"] = "Prompt"
                elif "LanguageModelComponent" in node_id:
                    node_data["type"] = "LanguageModelComponent"
                elif "ChatOutput" in node_id:
                    node_data["type"] = "ChatOutput"

    # Ensure edges have proper structure
    edges = workflow_data.get("edges", [])
    for edge in edges:
        if "selected" not in edge:
            edge["selected"] = False
        if "animated" not in edge:
            edge["animated"] = False

        # Ensure data field exists
        if "data" not in edge:
            edge["data"] = {}

    return workflow_data


async def generate_workflow_with_llm(
    user_message: str,
    conversation_history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Generate workflow JSON using LLM based on user requirements.

    Args:
        user_message: The user's requirement message
        conversation_history: Previous conversation messages

    Returns:
        Generated workflow JSON data
    """
    settings_service = get_settings_service()

    # Get OpenAI API key from settings
    # api_key = settings_service.settings.openai_api_key
    api_key = "ms-0d6c23a7-6bc2-442a-b01f-ae10f95d3e65"
    if not api_key:
        raise ValueError("OpenAI API key not configured. Please set OPENAI_API_KEY environment variable.")

    # Load system prompt
    system_prompt = load_system_prompt()

    # Initialize LLM
    # Try ModelScope API first, fallback to OpenAI if needed
    # try:
    #     from langchain_google_genai import ChatGoogleGenerativeAI
    #     await logger.adebug("Initializing LLM with ModelScope API...")
    # llm = ChatOpenAI(
    #     model="Qwen/Qwen2.5-72B-Instruct",
    #     temperature=0.3,
    #     openai_api_key="ms-0d6c23a7-6bc2-442a-b01f-ae10f95d3e65",
    #     base_url="https://api.modelscope.cn/v1",
    #     timeout=60.0,  # Add timeout
    # )
    #     llm = ChatGoogleGenerativeAI(
    #         model="gemini-2.5-flash-lite",
    #         google_api_key="AIzaSyC_lesT3WXoC6d_0OVf9FLB_RwcvhZwnys",  # 你的 Google API Key
    #         temperature=0.3,
    #     )
    #     await logger.adebug("ModelScope LLM initialized successfully")
    # except Exception as e:
    #     await logger.awarning(f"Failed to initialize ModelScope LLM: {e}, falling back to OpenAI")
    #     # Fallback to OpenAI
    #     if not api_key:
    #         raise ValueError("OpenAI API key not configured. Please set OPENAI_API_KEY environment variable.")
    #     llm = ChatOpenAI(
    #         model="gpt-4o-mini",
    #         temperature=0.3,
    #         openai_api_key=api_key,
    #     )

    # Build messages
    # messages = [SystemMessage(content=system_prompt)]

    # # Add conversation history
    # if conversation_history:
    #     for msg in conversation_history:
    #         if msg.get("role") == "user":
    #             messages.append(HumanMessage(content=msg.get("content", "")))
    #         elif msg.get("role") == "assistant":
    #             messages.append(SystemMessage(content=msg.get("content", "")))

    # # Add current user message
    # messages.append(HumanMessage(content=user_message))

    # ====================== Call LLM
    # await logger.adebug("Calling LLM to generate workflow...")
    # try:
    #     response = await llm.ainvoke(messages)
    #     response_text = response.content
    #     if not response_text:
    #         raise ValueError("Empty response from LLM")
    #     await logger.adebug(f"LLM response received, length: {len(response_text)}")
    # except Exception as e:
    #     error_msg = f"LLM invocation failed: {str(e)}"
    #     await logger.aerror(error_msg)
    #     await logger.aexception("LLM call error")
    #     raise ValueError(f"Failed to call LLM: {str(e)}") from e

    # ====================== TEST： 直接读取答案
    # 读取并解析 JSON
    json_file = Path(
        "/home/gys/catl/langflow/src/backend/base/langflow/agent_workflow/answer.json"
    )
    import asyncio

    # 在线程池中执行阻塞操作
    def _load_json():
        with json_file.open("r", encoding="utf-8") as f:
            return json.load(f)

    workflow_data = await asyncio.to_thread(_load_json)
    await logger.ainfo(f"Successfully loaded answer.json, Response text length: {len(workflow_data)}")

    # ====================== LLM输出结果的json提取与格式验证
    # Extract JSON from response (handle markdown code blocks)
    # json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL)
    # if json_match:
    #     json_str = json_match.group(1)
    # else:
    #     # Try to find JSON object directly
    #     json_match = re.search(r"(\{.*\})", response_text, re.DOTALL)
    #     if json_match:
    #         json_str = json_match.group(1)
    #     else:
    #         raise ValueError("No JSON found in LLM response")
    # # Parse JSON
    # try:
    #     workflow_data = json.loads(json_str)
    # except json.JSONDecodeError as e:
    #     await logger.aerror(f"Failed to parse JSON from LLM response: {e}")
    #     await logger.adebug(f"Response text: {response_text}")
    #     raise ValueError(f"Invalid JSON in LLM response: {e}") from e

    # Validate workflow
    is_valid, error_msg = validate_workflow_json(workflow_data)
    if not is_valid:
        await logger.aerror(f"Workflow validation failed: {error_msg}")
        raise ValueError(f"Invalid workflow structure: {error_msg}")

    # Format workflow
    workflow_data = format_workflow_json(workflow_data)

    await logger.ainfo("Successfully generated workflow from LLM")
    return workflow_data
