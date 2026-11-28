"""The entry points that drive the modules (#248): the web API (FastAPI, `api`) and the command line (Typer + Rich, `cli`). They only translate — a
request or a command into a call to a use case, and its answer, or its error, back — and they give each use case its adapters."""
