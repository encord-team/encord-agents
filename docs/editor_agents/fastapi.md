!!! warning
    ⚠️ Before we begin, please make sure that you have [authentication](../authentication.md) covered.

!!! info
    This example shows the general structure of how to build a FastAPI application with `encord-agents`.
    For concrete implementations of agents with specific abilities, please see the [examples section](examples/index.md).

## Create a project

Create a new project:

```shell
mkdir my_project
cd my_project
```

Create and source a new virtual environment.

```
python -m venv venv
source venv/bin/activate
```

Install the dependencies.

```shell
python -m pip install "fastapi[standard]" encord-agents
```

## Develop your agent

Create a `main.py` file with the following template:

```python title="main.py"
from typing_extensions import Annotated

from encord.objects.ontology_labels_impl import LabelRowV2
from encord_agents import FrameData
from encord_agents.fastapi import dep_label_row

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(
            CORSMiddleware,
            allow_origins=["*", "https://app.encord.com"],
)

@app.post("/my_agent")
def my_agent(
    frame_data: FrameData,
    label_row: Annotated[LabelRowV2, Depends(dep_label_row)],
):
    # ... Do your edits to the labels
    label_row.save()
```

Fill in the function `my_agent` with what you want to happen when your agent is triggered.

!!! tip
    💡 Notice that you can inject multiple different [dependencies](../reference/editor_agents.md#encord_agents.fastapi.dependencies) into the function if you want.

You can find multiple examples of what can be done with editor agents [here](../editor_agents/examples/index.md).

## Test the agent

First, run the agent locally, such that it can be triggered.

```shell
ENCORD_SSH_KEY_FILE=/path/to/your_private_key \
    fastapi dev main.py --port 8080
```

!!! info
    Effectively, this means starting an API that lives at `localhost:8080/my_agent` and expects a POST request with `JSON` data of the following format:
    ```json
    {
        "project_hash": "<project_hash>",
        "data_hash": "<data_hash>",
        "frame": <frame_number>
    }
    ```

To hit that agent endpoint, open the [Label Editor](https://docs.encord.com/platform-documentation/Annotate/annotate-label-editor) in your browser on a frame for which you want to test your agent. Copy the URL.

Open a new terminal in the `my_project` directory.
Then, run

```shell
source venv/bin/activate
encord-agents test local my_agent <the_pasted_url>
```

Refresh the label editor in your browser to see the effect that you applied to the `label_row: LabelRowV2` happening.

## Deployment

TODO
