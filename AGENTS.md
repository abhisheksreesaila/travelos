# Project agent memory

This file is the project's committed home for project-intrinsic agent knowledge: build, test, release, architecture, and sharp-edge notes that should travel with the code.

- App entry point and route/UI composition: `main.py`; start it with `python main.py` after installing the `pyproject.toml` dependencies.
- Tenant-scoped fixture persistence is implemented in `data.py` with fh-saas host and tenant SQLite databases; generated runtime databases belong under ignored `data/` (or `TRAVELOS_DATA_DIR`).
- Run the deterministic local smoke suite with `python -m unittest discover -s tests -v`. See `README.md` for the product journey and explicitly deferred provider integrations.

## Maintaining this file

Keep this file for knowledge useful to almost every future agent session in this project.
Do not repeat what the codebase already shows; point to the authoritative file or command instead.
Prefer rewriting or pruning existing entries over appending new ones.
When updating this file, preserve this bar for all agents and keep entries concise.
