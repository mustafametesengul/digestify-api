# Development

Install dependencies:

```bash
uv sync
```

Sort imports:

```bash
uv run ruff check --select I --fix
```

Format code:

```bash
uv run ruff format
```

Generate a new migration:

```bash
uv run alembic revision --autogenerate -m "Migration message"
```

Apply all migrations:

```bash
uv run alembic upgrade head
```

Roll back one migration:

```bash
uv run alembic downgrade -1
```

Roll back all migrations:

```bash
uv run alembic downgrade base
```

Run unit tests:

```bash
uv run pytest
```
