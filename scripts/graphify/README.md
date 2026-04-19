# scripts/graphify

Cross-platform helpers (Windows / macOS / Linux) for building a knowledge graph
of any codebase using [graphify](https://github.com/safishamsi/graphify).

These are a fallback for when you want a fast, free, code-only build without
running the full `/graphify` skill in Claude Code. **For the full pipeline that
also reads docs, papers, and images via AI subagents, type `/graphify` inside
Claude Code -- this folder does not replace that.**

## Install once

```
pip install graphifyy
```

(Yes, double `y`. The package on PyPI is `graphifyy`; the unrelated single-`y`
package is not affiliated with the project.)

## What's here

| File | Purpose |
|---|---|
| [`build_graph.py`](build_graph.py) | Build the graph end-to-end: detect files, AST-extract code, cluster, write report + JSON + HTML. AST only -- no tokens spent. |
| [`list_communities.py`](list_communities.py) | Print every community's contents so you can pick human-readable names. |

## Usage

### Build a graph of the whole repo

```
python scripts/graphify/build_graph.py
```

### Build for a specific subfolder

```
python scripts/graphify/build_graph.py src
```

### Exclude folders you don't want indexed

```
python scripts/graphify/build_graph.py . --exclude plots --exclude data --exclude node_modules
```

`--exclude` matches any folder name anywhere in the path; pass it multiple times.

### Other flags

```
--no-viz           Skip generating graph.html
--out custom-dir   Use a different output directory (default: graphify-out)
--benchmark        Also print the token-reduction benchmark
```

### Inspect communities (helps with naming them)

```
python scripts/graphify/list_communities.py
python scripts/graphify/list_communities.py graphify-out/graph.json --max-samples 15
```

## Outputs

After a successful run, `graphify-out/` will contain:

| File | What it is | Commit? |
|---|---|---|
| `graph.json` | Raw graph data -- **this is what you hand to other AI models** | yes |
| `GRAPH_REPORT.md` | Human-readable audit: god nodes, surprising connections, communities | yes |
| `graph.html` | Interactive visualization, open in any browser | optional |
| `manifest.json` | Lets `/graphify --update` know what changed | yes |
| `cost.json` | Local token-usage log | no (gitignored) |
| `cache/` | Semantic extraction cache (only used by `/graphify`) | no (gitignored) |

The `.gitignore` at the project root already excludes the transient bits.

## When to use this script vs `/graphify` in Claude Code

| Want... | Use |
|---|---|
| Fast code-only rebuild, no LLM cost | this script |
| CI / pre-commit / cron job | this script |
| Predictable, scriptable, no Claude needed | this script |
| Read docs / papers / image content into the graph | `/graphify` (uses AI subagents) |
| Auto-label communities with meaningful names | `/graphify` |
| Ask questions against the graph | `/graphify query "..."` |

## Drop-in to another project

Copy the entire `scripts/graphify/` folder. No paths or names are
hardcoded -- it works in any repo as long as `pip install graphifyy` is
done in that environment. Add the gitignore lines from this repo's
`.gitignore` (the `# graphify` section) to that project too.
