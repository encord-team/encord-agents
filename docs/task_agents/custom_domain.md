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

## STEP 3: If you are using the Encord Client in your Task agent, pass in your domain 

Since Encord is a separate package than Encord-Agents, when creating an Encord Client, you'll also need to declare the domain

```python
from encord import EncordUserClient

DOMAIN = "https://api.us.encord.com"

# You can get your Encord Key here: https://docs.encord.com/platform-documentation/Annotate/annotate-api-keys
client = EncordUserClient.create_with_ssh_private_key(
    ssh_private_key="<private_key>",
    domain=DOMAIN
)
```
