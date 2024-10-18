# Google Cloud Run Functions

> ⚠️ Before we begin, please make sure that you have [authentication](/authentication) covered.

## Create a project

Create a new project:

```shell
mkdir my_project
cd my_project
```

Create a new virtual environment.

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

Second, open the [Label Editor](https://docs.encord.com/platform-documentation/Annotate/annotate-label-editor) on a frame for which you want to test your agent. Copy the URL.

Open a new terminal in the `my_project` directory.
Then, run

```shell
source venv/bin/activate
encord-agents test local my_agent <editor_url>
```

Refresh the browser to see the effect happening.

## Deployment

This is an example of how you could deploy the agent to the cloud.
Here are the official [Google Deploy Docs](https://cloud.google.com/functions/docs/create-deploy-gcloud).
There are a couple of things that you need to pay attention to:

- You must make sure to authenticate `gcloud` and select the appropriate project first
- You should configure a secret with the ssh_key content. Please see [Google Secrets docs](https://cloud.google.com/functions/docs/configuring/secrets)

A deployment command would look similar to this:

```shell
gcloud functions deploy my_agent \\
    --entry-point my_agent \\
    --runtime python311 \\
    --trigger-http \\
    --allow-unauthenticated \\
    --gen2 \\
    --region europe-west2 \\
    --set-secrets="ENCORD_SSH_KEY=SERVICE_ACCOUNT_KEY:latest"
```

Notice how we set secrets (the ssh key that the agent should use).
