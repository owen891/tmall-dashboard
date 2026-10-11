<!-- GRAPHFLOW:BEGIN managed block — edit outside these markers only -->
# GraphFlow for Claude Code

Use GraphFlow as a local orchestration and context service.

## Recommended setup

Add a local MCP server entry that launches GraphFlow over stdio:

```json
{
  "mcpServers": {
    "graphflow": {
      "command": "npx",
      "args": ["-y", "--package=@roarpeng/graphflow", "graphflow-mcp"]
    }
  }
}
```

During repository development you can also point Claude Code at this checkout:

```json
{
  "mcpServers": {
    "graphflow": {
      "command": "npm",
      "args": ["run", "start:mcp"],
      "cwd": "."
    }
  }
}
```

## Usage guidance

- Ask GraphFlow to plan before broad changes: `graphflow_plan`.
- Ask GraphFlow to compress and anchor code context: `graphflow_context`.
- Always pass `rootDir` = this project's absolute path. **Never** pass your home directory, AppData, or an unexpanded `${workspaceFolder}` placeholder — GraphFlow refuses unsafe workspace roots. If a call answers `unsafe workspace root`, retry the same call without `rootDir` (the server then uses its configured workspace).
- Ask GraphFlow to inspect graph state or skill learnings when the repo history matters.
- After executing work from a `graphflow_run` `executionDescriptor`, **must** call `graphflow_report_outcome` with the `episodeId` from the run result, a `success` boolean, and optional `lessons` to close the skill flywheel loop.
- Fall back to `graphflow ... --json` only if MCP is not available (including `graphflow --json outcome report <episodeId> <success>`).

DeepSeek Harness: `dsh plugin --profile web add @roarpeng/graphflow` (or `npx @roarpeng/graphflow install` when `~/.dsh` exists).
<!-- GRAPHFLOW:END -->
