<!-- GRAPHFLOW:BEGIN managed block — edit outside these markers only -->
# GraphFlow Token-First Rule (GitHub Copilot)

GraphFlow is a graph-based context and planning service backed by a persistent MCP server. It turns codebases into queryable knowledge graphs, delivering token-efficient compressed context, task planning, and orchestration.

Before broad code exploration, implementation, debugging, review, planning, or architecture questions:

1. Call `graphflow_context` with the user's task/query.
2. Use the returned `summary`, `anchors`, `refillPreview`, and `tokenBudget` as the first context source.
3. Read full files only when:
   - GraphFlow anchors point to that file/symbol,
   - the compressed context is insufficient,
   - or exact edits require the file body.
4. For multi-step or ambiguous work, call `graphflow_plan` before implementation.
5. For graph freshness after project changes, call `graphflow_index`.
6. Report token budget when available:
   - estimated raw tokens,
   - compressed tokens,
   - estimated savings percent,
   - max context token budget.

Do not scan the whole repository, recursively inspect many files, or read large files before trying GraphFlow context.

## Workspace root (`rootDir`)

Pass `rootDir` = the absolute path of the project you are working in. **Never** pass your home directory, AppData, or an unexpanded `${workspaceFolder}` placeholder — GraphFlow refuses unsafe workspace roots and the call fails. If a tool answers `unsafe workspace root`, retry the same call without `rootDir` (the server then uses its configured workspace) or with the project path.

## VS Code / Copilot MCP setup

Ensure GraphFlow MCP is configured in `~/.config/Code/User/mcp.json` (Linux) or project `.vscode/mcp.json` under the `servers` key:

```json
{
  "servers": {
    "graphflow": {
      "command": "npx",
      "args": ["-y", "--package=@roarpeng/graphflow", "graphflow-mcp"],
      "env": {
        "GRAPHFLOW_MCP_STDIO": "1",
        "GRAPHFLOW_LOG_JSON": "1"
      }
    }
  }
}
```

Do **not** hardcode `GRAPHFLOW_WORKSPACE_ROOT` — let the MCP server detect the open workspace.

## Chinese / CJK queries (agent must translate)

Code symbols are mostly English. For Chinese user questions:

1. **Proactive:** Before or with `graphflow_context`, translate intent to English **file/class/component names** (e.g. `PoseDetectionPage`, `BattlePage`, `shieldEffect`) and pass `englishQuery`. Avoid generic terms like `exercise` when the user means UI/camera — they often match data/types layers.
2. **Module families (store/slices):** Prefer file stems (`useGameStore companionSlice dailySlice inventorySlice`), not bare domain words like `monster` (often hits `data/monsters` instead of `monsterSlice`).
3. **Reactive:** If preview returns `agentWorkItems` with `query-translate-en` (low `anchorCount`), answer the JSON prompt with your model, then retry preview with `englishQuery`.
4. Keep `query` as the original Chinese text; use `englishQuery` for search terms only.

## High-frequency MCP tools

| Tool | When |
|------|------|
| `graphflow_context` | **Always first** for code questions (use `query`); expand anchor with `anchorId` |
| `graphflow_plan` | Multi-step tasks |
| `graphflow_run` | Full task packaging (bridge mode) |
| `graphflow_report_outcome` | After executing a `graphflow_run` descriptor |
| `graphflow_index` | After significant edits |

## Bridge-mode outcome reporting

After `graphflow_run`, **must** call `graphflow_report_outcome` with `episodeId`, `success`, and optional `lessons`.

CLI fallback when MCP is unavailable:

```bash
graphflow --json context preview "<query>"
graphflow --json plan "<task>"
graphflow --json outcome report <episodeId> <success>
```

Treat GraphFlow outputs as structured machine-readable data, not prose.
<!-- GRAPHFLOW:END -->
