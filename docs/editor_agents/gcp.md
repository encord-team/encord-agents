!!! warning
    Before you start, ensure that you can [authenticate](../authentication.md) with Encord.

!!! info
    The following example shows the general structure of how to build a GCP cloud function.
    For concrete implementations of agents with specific abilities, see the [examples section](./examples/index.md).

## STEP 1: Create a Project

1. Create a new Encord Project:

    ```shell
    mkdir my_project
    cd my_project
    ```

2. Create and source a new virtual environment.

    ```
    python -m venv venv
    source venv/bin/activate
    ```

3. Create a requirements file.

    ```requirements title="requirements.txt"
    functions-framework
    encord-agents
    ```

4. Install dependencies.  

    ```shell
    python -m pip install -r requirements.txt
    ```

## STEP 2: Define the Agent

Create a `main.py` file using the following template:

```python title="main.py"
from encord.objects.ontology_labels_impl import LabelRowV2

from encord_agents.core.data_model import FrameData
from encord_agents.gcp import editor_agent


@editor_agent()
def my_agent(frame_data: FrameData, label_row: LabelRowV2) -> None:
    ...
    # label_row.save()
```

Complete the `my_agent` function with the logic you want to execute when the agent is triggered.

!!! tip
    You can inject multiple different [dependencies](../reference/editor_agents/#encord_agents.gcp.dependencies) into the function if necessary.

You can find multiple examples of what can be done with editor agents [here](/editor_agents/examples).

## STEP 3: Test the Agent

Trigger the agent by running it locally.

```shell
ENCORD_SSH_KEY_FILE=/path/to/your_private_key \
    functions-framework --target=my_agent --debug --source main.py
```

!!! info
    This means starting an API at `localhost:8080/my_agent` that expects a POST request with `JSON` data with the following format:
    ```json
    {
        "projectHash": "<project_hash>",
        "dataHash": "<data_hash>",
        "frame": <frame_number>
    }
    ```

To test the agent endpoint, open the [Label Editor](https://docs.encord.com/platform-documentation/Annotate/annotate-label-editor){ target="\_blank", rel="noopener noreferrer" } in your browser on a frame where you want to run the agent. Then, copy the URL.

Open a new terminal in the `my_project` directory and run:

```shell
source venv/bin/activate
encord-agents test local my_agent '<the_pasted_url>'
```

!!! warning
    Notice the single quotes around `<the_pasted_url>`. They are important and should be there because you might copy a url with, e.g., an `&` character that have a [special meaning](https://www.howtogeek.com/439199/15-special-characters-you-need-to-know-for-bash/#amp-background-process){ target="_blank", rel="noopener noreferrer" } if it is not within a string (or escaped).

Refresh the Label Editor in your browser to see the effect.

## STEP 4: Deployment

To go from development to production, you must deploy your agent on the Google infrastructure.

The following example shows how you can deploy the agent to the cloud.

```shell
gcloud functions deploy my_agent \
    --entry-point my_agent \
    --runtime python311 \
    --trigger-http \
    --allow-unauthenticated \
    --gen2 \
    --region europe-west2 \
    --set-secrets="ENCORD_SSH_KEY=SERVICE_ACCOUNT_KEY:latest"
```

Notice how secrets are set (the SSH key that the agent should use).

See the official [Google run function deploy docs](https://cloud.google.com/functions/docs/create-deploy-gcloud){ target="\_blank", rel="noopener noreferrer" } for more information.

There are a couple of things that you need to pay attention to:

* You must make sure to authenticate `gcloud` and select the appropriate project first
* You should configure a secret with the ssh_key content. See [Google Secrets docs](https://cloud.google.com/functions/docs/configuring/secrets){ target="\_blank", rel="noopener noreferrer" }


