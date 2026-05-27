# aria-et

Eye-tracking paradigms for the ARIA ABCCT battery recreation.

## Development

```bash
uv sync --dev
uv run pytest
uv run aria-et list-tasks
```

The current scaffold exposes the intended battery order without opening PsychoPy
windows or requiring a live Tobii eye tracker.
