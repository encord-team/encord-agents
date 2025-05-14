!!! info
    The following code is for users using Encord with the US domain (`https://api.us.encord.com`) or their own private VPC (Virtual Private Cloud).

## STEP 1: Set the `ENCORD_DOMAIN` Environment variable


This will be the domain to the Encord API, not the front-end app. 

If running locally 
```shell
export ENCORD_DOMAIN=https://api.us.encord.com
```

If running in a Python project 
```python
import os

os.environ["ENCORD_DOMAIN"] = "https://api.us.encord.com"
```


## STEP 2: Set the `ENCORD_SSH_KEY` or `ENCORD_SSH_KEY_FILE` Environment variables

If running locally 

```shell
export ENCORD_SSH_KEY_FILE="path/to/your/key"
```
or

```shell
export ENCORD_SSH_KEY="<your key>"
```

If deploying with a GCP cloud function, create a GCP secret & pass in the Key 
```python
import os

os.environ["ENCORD_SSH_KEY"] = "<your key>"
# or
os.environ["ENCORD_SSH_KEY_FILE"] = "path/to/your/file"
```

## STEP 3: If you are using the Encord Client in your Task agent, make sure you instantiate the client from the agent

Since Encord is a separate package than Encord-Agents, when leveraging an Encord Client, you'll also need to use the client connected to the agent.

For tasks that need the Encord client for every operation, we recommend:
```python
@app.post("/my-agent")
def my_agent(user_client: Annotated[EncordUserClient, Depends(dep_user_client)]):
    # use agent to get project, dataset, etc 
```

If you only need the client once to do batch processing or filtering, you can fetch the existing client from the agents library:

```python
from encord_agents.core.utils import get_user_client

encord_user_client = get_user_client()
```