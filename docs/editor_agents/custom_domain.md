!!! info
    The following code is for users using Encord with the US domain (`https://api.us.encord.com`) or their own private VPC (Virtual Private Cloud).

## STEP 1: Set the `ENCORD_DOMAIN` Environment variable

This will be the domain to the Encord API, not the front-end app. 

If running locally 
```shell
export ENCORD_DOMAIN=https://api.us.encord.com
```
If deploying with a GCP cloud function, create a GCP secret & pass in the domain 
```shell
--set-secrets="ENCORD_SSH_KEY=YOUR_GCP_STORED_KEY:latest,ENCORD_DOMAIN=YOUR_GCP_STORED_DOMAIN"
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
```shell
--set-secrets="ENCORD_SSH_KEY=YOUR_GCP_STORED_KEY:latest,ENCORD_DOMAIN=YOUR_GCP_STORED_DOMAIN"
```

## STEP 3: Pass in the Domain to the Editor Agent declaration

You'll need to pass in the Encord Front-end domain into the `@editor_agent` declaration so that the function respects CORS:

```python
@editor_agent(custom_cors_regex="https://app.us.encord.com") # Or the domain of your custom FE
```