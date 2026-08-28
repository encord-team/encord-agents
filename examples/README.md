# Examples

Runnable examples for the `encord-agents` library. Each one is self-contained — copy it out,
fill in your project hash, ontology and stage UUIDs, and run it.

For the concepts behind these examples, see the
[Encord documentation](https://docs.encord.com/platform-documentation/).

## `notebooks/`

Colab-ready notebooks covering pre-labelling, routing, transcription, captioning and
label transfer. Open any of them directly in Colab from the GitHub view.

## `editor_agents/`

Editor agents respond to a request from the label editor. Grouped by where you host them:

| Directory  | Hosting                  |
| ---------- | ------------------------ |
| `gcp/`     | Google Cloud Functions   |
| `fastapi/` | Your own FastAPI service |
| `modal/`   | Modal                    |

## `task_agents/`

Task agents move tasks through a project workflow.

| Path                                   | What it shows                                                        |
| -------------------------------------- | -------------------------------------------------------------------- |
| `celery/`                              | Distributed `QueueRunner` on Celery + RabbitMQ                       |
| `modal/`                               | `QueueRunner` on Modal, and a batch job-processing variant           |
| `prioritize_by_data_title_specific.py` | A minimal local `Runner` that sets task priority from the data title |

## Notes

- `ruff.toml` narrows the line length for this directory; it extends the root `pyproject.toml`.
- `examples/` is excluded from `mypy` — these files are illustrative and use placeholder
  identifiers rather than real ones.
