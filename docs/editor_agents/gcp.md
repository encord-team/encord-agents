# Google Cloud Run Functions

!!! warning
    ⚠️ Before we begin, please make sure that you have [authentication](/authentication) covered.

!!! info
    This example shows the general structure of how to build a GCP cloud function.
    For concrete implementations of agents with specific abilities, please see the [examples section](../examples/).

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

Make a requirements file:

```requirements title="requirements.txt"
functions-framework
encord-agents
```

Install the dependencies.

!!! warning
    Make sure you sourced the environment above. Otherwise, the dependencies will be installed globally.    

```shell
python -m pip install -r requirements.txt
```

## Develop your agent

Create a `main.py` file with the following template:

```python title="main.py"
from encord.objects.ontology_labels_impl import LabelRowV2

from encord_agents.core.data_model import FrameData
from encord_agents.gcp import editor_agent


@editor_agent()
def my_agent(frame_data: FrameData, label_row: LabelRowV2) -> None:
    ...
    # label_row.save()
```

Fill in the function `my_agent` with what you want to happen when your agent is triggered.

> 💡 Notice that you can inject multiple different [dependencies](/reference/editor_agents/#encord_agents.gcp.dependencies) into the function if you want.

You can find multiple examples of what can be done with editor agents [here](/editor_agents/examples).

## Test the agent

First, run the agent locally, such that it can be triggered.

```shell
ENCORD_SSH_KEY_FILE=/path/to/your_private_key \
    functions-framework --target=my_agent --debug --source main.py
```

!!! info
    Effectively, this means starting an API that lives at `localhost:8080/my_agent` and expects a POST request with `JSON` data of the following format:
    ```json
    {
        "projectHash": "<project_hash>",
        "dataHash": "<data_hash>",
        "frame": <frame_number>
    }
    ```

To hit that agent endpoint, open the [Label Editor](https://docs.encord.com/platform-documentation/Annotate/annotate-label-editor){ target="\_blank", rel="noopener noreferrer" } in your browser on a frame for which you want to test your agent. Copy the URL.

Open a new terminal in the `my_project` directory.
Then, run

```shell
source venv/bin/activate
encord-agents test local my_agent '<the_pasted_url>'
```

!!! warning
    Notice the single quotes around `<the_pasted_url>`. They are important and should be there because you might copy a url with, e.g., an `&` character that have a [special meaning](https://www.howtogeek.com/439199/15-special-characters-you-need-to-know-for-bash/#amp-background-process){ target="_blank", rel="noopener noreferrer" } if it is not within a string (or escaped).

Refresh the label editor in your browser to see the effect that you applied to the `label_row: LabelRowV2` happening.

## Deployment

To go from development to production, you need to deploy your agent on the Google infrastructure.
This is an example of how you could deploy the agent to the cloud.

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

Notice how we set secrets (the ssh key that the agent should use).

Here are the official [Google run function deploy docs](https://cloud.google.com/functions/docs/create-deploy-gcloud){ target="\_blank", rel="noopener noreferrer" }.
There are a couple of things that you need to pay attention to:

- You must make sure to authenticate `gcloud` and select the appropriate project first
- You should configure a secret with the ssh_key content. Please see [Google Secrets docs](https://cloud.google.com/functions/docs/configuring/secrets){ target="\_blank", rel="noopener noreferrer" }


