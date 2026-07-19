#!/usr/bin/env python3

import asyncio
import os
import shutil
from pathlib import Path

from fastmcp.client.transports import StdioTransport
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider


async def main() -> None:
    token = os.environ.get("NEW_API_TOKEN")
    if not token:
        raise SystemExit("NEW_API_TOKEN is not set")

    command = shutil.which("awslabs.openapi-mcp-server")
    if not command:
        raise SystemExit("awslabs.openapi-mcp-server was not found in PATH")

    spec = Path(__file__).with_name("aiops-dashboard.openapi.yaml").resolve()
    dashboard_url = os.environ.get(
        "AIOPS_DASHBOARD_URL",
        "http://127.0.0.1:8789",
    )

    transport = StdioTransport(
        command=command,
        args=[
            "--api-name", "aiops-dashboard",
            "--api-url", dashboard_url,
            "--spec-path", str(spec),
            "--auth-type", "none",
            "--allow-insecure-http",
            "--allow-private-networks",
            "--allowed-spec-dirs", str(spec.parent),
            "--log-level", "ERROR",
        ],
    )

    model = OpenAIChatModel(
        os.environ.get("NEW_API_MODEL", "codex/gpt-5.5"),
        provider=OpenAIProvider(
            base_url=os.environ.get(
                "NEW_API_BASE_URL",
                "http://127.0.0.1:3500/v1",
            ),
            api_key=token,
        ),
    )

    agent = Agent(
        model,
        toolsets=[MCPToolset(transport)],
        instructions=(
            "Always use the MCP tools getHealth and getReadiness. "
            "Report the AI-OPS dashboard state concisely."
        ),
    )

    result = await agent.run("Check the current AI-OPS dashboard state.")
    print(result.output)


if __name__ == "__main__":
    asyncio.run(main())
