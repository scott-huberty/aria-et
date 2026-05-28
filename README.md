# aria-et

Eye-tracking paradigms for the ARIA ABCCT battery recreation.

## Development

```bash
mamba env update -n aria-et -f environment.yml
conda activate aria-et
python -m pip install --no-build-isolation -e .
python -m pytest
aria-et list-tasks
```

The core development environment intentionally excludes PsychoPy and Tobii
dependencies. Install PsychoPy separately in the runtime environment used for
display demos.
