!!! warning
    Before you start, ensure that you can [authenticate](../authentication.md) with Encord and your [AWS CLI is authenticated](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-authentication.html){ target="_blank", rel="noopener noreferrer" }.

!!! info
    The following example shows the general structure of how to build an AWS Lambda function.
    For concrete implementations of agents with specific abilities, see the [examples section](./examples/index.md).

There are two different ways in which you can create lambda functions. 

1. [Using a zip upload](#building-a-lambda-function-using-zip-upload)
2. [Using a Docker container](#building-a-lambda-function-with-docker)

They have different applications and properties. 
Before you dive into one of the examples, please consider the properties in the table below.

| Type | File size limits | Ease of use |
| :-- | :---: | :---: |
| [Zip upload](#building-a-lambda-function-using-zip-upload) | 50MB (250MB unzipped) | `easier` |
| [Docker](#building-a-lambda-function-with-docker) | NA | `harder` |

AWS limits zip uploads to 50MB (250MB uncompressed), which means that if you want to use, e.g., computer vision capabillities (like `pip install encord-agents[vision]`), the bundle can very quickly become too large; forcing you to use Docker.
Other complications are that if you use specific dependencies that use C/C++ code under the hood, you have to install them with the right cpu architecture, which might cause you to have to upload your function before you can test it.

More detailed AWS Documentation on python lambda functions can be found [here](https://docs.aws.amazon.com/lambda/latest/dg/lambda-python.html){ target="_blank", rel="noopener noreferrer" }.

## Building a lambda function using zip upload

The full AWS lambda documentation for zip files is available [here](https://docs.aws.amazon.com/lambda/latest/dg/python-package.html){ target="_blank", rel="noopener noreferrer" }.

### STEP 1: Create a local Project

Start by creating a local project. 
It will have two directories, a local virtual environment (named `venv` in this example) and a `package` directory 
with the cpu-architecture-specific dependencies that will work int the cloud infrastructure.

First, let's create the virtual environment and install `encord-agents`. Please see the [installation docs](../installation.md) for more information.

```shell
mkdir my_project
cd my_project
python -m venv venv
source venv/bin/activate
pip install encord-agents
deactivate
```

Next, let's create the "mirror" package directory for the upload.
Note that it's advised to also install `boto3` which is the AWS SDK (that will live in the lambda function anyway).
The reason is that then the `boto3` dependency doesn't change version when AWS updates it's infrastructure.

```shell
mkdir package
pip install \
  --platform manylinux2014_x86_64 \
  --target=package \
  --implementation cp \
  --python-version 3.12 \
  --only-binary=:all: --upgrade \
  encord-agents boto3
```

### STEP 2: Define the agent

Create a `lambda_function.py` file using the following template:

```python title="lambda_function.py"
from encord.objects.ontology_labels_impl import LabelRowV2

from encord_agents.core.data_model import FrameData
from encord_agents.aws import editor_agent


@editor_agent()
def lambda_handler(frame_data: FrameData, label_row: LabelRowV2) -> None:
    print(frame_data.model_dump_json())
    # label_row.save()
```

Note that it's important to name both the file as `lambda_function.py` and the function `lambda_handler` if you want to follow this example.
[Step 6](#step-6-upload-the-zip) will use the two names in the `--handler` argument.

Complete the `lambda_handler` function with the logic you want to execute when the agent is triggered.

!!! tip
    For more editor agent examples, see the [examples section](./examples/index.md).
    You can inject multiple different [dependencies](../reference/editor_agents/#encord_agents.aws.dependencies) into the function if necessary.

You can find multiple examples of what can be done with editor agents [here](./examples/index.md).

### STEP 3: (Optional) Test the agent locally

!!! warning
    We are testing against the `venv` and not the `package` that is uploaded to AWS, so we might see slight differences in the outcome.

In order to test your agent locally, you can add an `if __name__ == "__main__"` declaration in the end of the file as follows:

```python title="lambda_function.py"
# ... imports from before
@editor_agent()
def lambda_handler(frame_data: FrameData):
    print(frame_data.model_dump_json())
    
if __name__ == '__main__':
    event = {
        "body": {
            "projectHash": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "dataHash": "00000000-1111-2222-3333-444444444444",
            "frame": 0,
            "objectHashes": []
        }
    }
    lambda_handler(event, None)
```

Make sure to update the project and data hash to correspond to one of your assets.

!!! hint
    If you open the label editor in your browser and look at the url, it has this pattern:
    ```
    https://app.encord.com/label_editor/{projectHash}/{dataHash}
    ```

Then, run the file:
```shell
source venv/bin/activate
export ENCORD_SSH_KEY_FILE='/path/to/your/private-key-file'
python lambda_function.py
```

### STEP 4: Create the ZIP file

Create the zip file by first zipping what is in the `package` directory:

```shell
cd package
zip -r ../package.zip .
cd ..
```

Then add your lambda function to the zip file:

```shell
zip package.zip lambda_function.py
```

### STEP 5: Set up an execution role 

The lambda function needs permissions to execute. 
For that, we use an execution role.

Start by creating the configuration file `trust-policy.json` to be uploaded to aws.

```json title="trust-policy.json"
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

Then create a role with the trust policy:
```shell
aws iam create-role \
    --role-name lambda-execute-encord-agents \
    --assume-role-policy-document file://trust-policy.json
```

It should output something similar to the following JSON. Make sure to take a note of the `Arn`.

```json
{
  "Role": {
    "Path": "/",
    "RoleName": "lambda-execute-encord-agents",
    "RoleId": "AROAQ7BEARV2DSFT2E3PI",
    "Arn": "arn:aws:iam::061234567890:role/lambda-execute-encord-agents",
    "CreateDate": "2025-05-09T10:39:35+00:00",
    "AssumeRolePolicyDocument": {
      "Version": "2012-10-17",
      "Statement": [
        {
          "Effect": "Allow",
          "Principal": {
            "Service": "lambda.amazonaws.com"
          },
          "Action": "sts:AssumeRole"
        }
      ]
    }
  }
}
```

Next, attach the basic lambda execution role to the role.

```shell
aws iam attach-role-policy \
    --role-name lambda-execute-encord-agents \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
```

### STEP 6: Upload the zip

To upload the zip file to AWS, use the following command. Make sure to insert the `<lambda_function_name>` you want to use and the proper role `Arn` (the one we took a note of above):

```shell
aws lambda create-function --function-name <lambda_function_name> \
  --runtime python3.12 \
  --handler lambda_function.lambda_handler \
  --role arn:aws:iam::061234567890:role/lambda-execute-encord-agents \
  --zip-file fileb://package.zip
```

!!! hint
    If you want to modify your lambda, follow the steps above again but call the update method rather than the `create-function` from the AWS CLI.

    ```shell
    aws lambda update-function-code \
      --function-name <lambda_function_name> \
      --zip-file fileb://package.zip
    ```

Now, proceed to [Step A](#step-a-configure-public-endpoint) below to complete the setup.

## Building a lambda function with Docker

The full AWS documentation for building docker images for lambda functions with Python is available [here](https://docs.aws.amazon.com/lambda/latest/dg/python-image.html){ target="_blank", rel="noopener noreferrer" }.

### STEP 1: Create a local Project

Start by creating a local project directory.

```shell
mkdir my_project
cd my_project
```

Then add a `requirements.txt` file.

```text title="requirements.txt"
boto3
encord-agents
```

#### (Optional) local environment
If you want, you can create a local environment for testing before building the docker image.

```
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### STEP 2: Define the agent

Create a `lambda_function.py` file using the following template:

```python title="lambda_function.py"
from encord.objects.ontology_labels_impl import LabelRowV2

from encord_agents.core.data_model import FrameData
from encord_agents.aws import editor_agent


@editor_agent()
def lambda_handler(frame_data: FrameData, label_row: LabelRowV2) -> None:
    print(frame_data.model_dump_json())
    # label_row.save()
```

Note that for the example to work, you should name both the file as `lambda_function.py` and the function `lambda_handler`.
The Docker image will look for those particular names in [the next step](#step-3-build-the-docker-image).

Complete the `lambda_handler` function with the logic you want to execute when the agent is triggered.

!!! tip
    For more editor agent examples, see the [examples section](./examples/index.md).
    You can inject multiple different [dependencies](../reference/editor_agents/#encord_agents.aws.dependencies) into the function if necessary.

You can find multiple examples of what can be done with editor agents [here](./examples/index.md).

### STEP 3: Build the docker image

Create a `Dockerfile` with the following content.

```Dockerfile title="Dockerfile"
FROM public.ecr.aws/lambda/python:3.12

# Install the specified packages
COPY requirements.txt ${LAMBDA_TASK_ROOT}
RUN pip install -r requirements.txt

# Copy function code
COPY lambda_function.py ${LAMBDA_TASK_ROOT}

# Set the CMD to your handler 
# (could also be done as a parameter override outside of the Dockerfile)
CMD [ "lambda_function.lambda_handler" ]
```

Now build the image locally.

!!! note
    You need to have `docker` and `buildx` installed.

```shell
docker buildx build \
    --platform linux/amd64 \
    --provenance=false \
    -t encord-agents-my-agent-name:latest \
    .
```

### STEP 4: (Optional) Test the agent locally

To test the agent locally, you can spin up the container with the following command.

```shell
docker run \
    -e ENCORD_SSH_KEY="$(cat /path/to/your/private-key-file)" \
    -p 9000:8080 \
    --platform linux/amd64 \
    -t encord-agents-my-agent-name:latest
```

The respective lines ensures that we

- Add the `ENCORD_SSH_KEY` env variable
- Map the port 8080 to your own local port (9000 in this example)
- AWS architecture needs to be `amd64` (or `arm64` [see aws docs](https://docs.aws.amazon.com/lambda/latest/dg/python-image.html#python-image-clients){ target="_blank", rel="noopener noreferrer" })
- Run the latest built image (`encord-agents-example:latest` in this example)

This will allow you to "hit" the function endpoint with a curl like the following.
The `functions/function/invocation` piece needs to be there; it's defined by Amazon.

```shell
curl "http://localhost:9000/2015-03-31/functions/function/invocations" \
    -X "POST" \
    -d '{
            "body": {
                "projectHash": "aaaaaaaa-ed79-4a1b-a0c1-b1b38ffb523c",
                "dataHash":"659c3a38-737f-4f56-a709-26ce01f5fd0b",
                "frame": 0,
                "objectHashes": []
            }
        }'
```

!!! note
    There's a long standing issue with Lambda docker containers that the "API" is different when running locally and 
    in the cloud. There are two relevant differences in this case.

    - `Content-Type`: Locally, the container expects a post request with `Content-Type: application/x-www-form-urlencoded` while the public url hosted by AWS expects `Content-Type: application/application-json`.
    - `POST` data: Locally, the post data needs to be `{"body": {... content dict}}` while the public url expects `{... content dict}`.

    As a consequence, the equivalent `curl` request for a publicly hosted lambda function would be:
    ```
    curl "https://<your_function_url_prefix>.lambda-url.eu-west-1.on.aws/" \
        -X "POST" \
        -H "Content-Type: application/json" \
        -d '{
            "projectHash": "aaaaaaaa-ed79-4a1b-a0c1-b1b38ffb523c",
            "dataHash":"659c3a38-737f-4f56-a709-26ce01f5fd0b",
            "frame": 0,
            "objectHashes": []
        }'
    ```
    See [the Function URL section](#step-a-configure-public-endpoint) for more information on how to get the public endpoint.


### Step 5: Prepare ECR container repository

To be able to associate a lambda function with your container, the container needs to be uploaded to the AWS Elastic Container Registry (ECR).
For that, we need a container repository. 

Run the `aws get-login-password` command to authenticate the Docker CLI to your Amazon ECR registry.

- Set the `--region` value to the AWS Region where you want to create the Amazon ECR repository (we use `eu-west-1` in this example).
- Replace 111122223333 with your AWS account ID.

```shell
aws ecr get-login-password --region eu-west-1 | docker login --username AWS --password-stdin 111122223333.dkr.ecr.eu-west-1.amazonaws.com
```

Create a repository in Amazon ECR using the create-repository command.

```shell
aws ecr create-repository \
    --repository-name <your-lambda-function-name> \
    --region us-east-1 \
    --image-scanning-configuration scanOnPush=true \
    --image-tag-mutability MUTABLE
```

If successful, you see a response like this:

```
{
    "repository": {
        "repositoryArn": "arn:aws:ecr:us-east-1:111122223333:repository/<your-lambda-function-name>",
        "registryId": "111122223333",
        "repositoryName": "<your-lambda-function-name>",
        "repositoryUri": "111122223333.dkr.ecr.us-east-1.amazonaws.com/<your-lambda-function-name>",
        "createdAt": "2025-05-12T10:39:01+00:00",
        "imageTagMutability": "MUTABLE",
        "imageScanningConfiguration": {
            "scanOnPush": true
        },
        "encryptionConfiguration": {
            "encryptionType": "AES256"
        }
    }
}
```

Copy the `repositoryUri` from the output.

### Step 6: Upload the local docker image

Run the `docker tag` command to tag your local image into your Amazon ECR repository as the latest version. 
In the following command:

- `encord-agents-my-agent-name:latest` is the name and tag of your local Docker image. This is the image name and tag that you specified in the `docker build` command [above](#step-3-build-the-docker-image).
- Replace <ecr-repository-uri> with the `repositoryUri` that you copied [above](#step-5-prepare-ecr-container-repository). Make sure to include `:latest` at the end of the URI.

```shell
docker tag encord-agents-my-angent-name:latest <ecr-repository-uri>:latest
```

Now that the tag lines up with ECR, we can push that tag.
Run the `docker push` command to deploy your local image to the Amazon ECR repository. 
Make sure to include `:latest` at the end of the repository URI.

```shell
docker push 111122223333.dkr.ecr.us-east-1.amazonaws.com/hello-world:latest
```


### STEP 7: Set up an execution role 

The lambda function needs permissions to execute. 
For that, we use an execution role.

Start by creating the configuration file `trust-policy.json` to be uploaded to aws.

```json title="trust-policy.json"
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

Then create a role with the trust policy:
```shell
aws iam create-role \
    --role-name lambda-execute-encord-agents \
    --assume-role-policy-document file://trust-policy.json
```

It should output something similar to the following JSON. Make sure to take a note of the `Arn`.

```json
{
  "Role": {
    "Path": "/",
    "RoleName": "lambda-execute-encord-agents",
    "RoleId": "AROAQ7BEARV2DSFT2E3PI",
    "Arn": "arn:aws:iam::061234567890:role/lambda-execute-encord-agents",
    "CreateDate": "2025-05-09T10:39:35+00:00",
    "AssumeRolePolicyDocument": {
      "Version": "2012-10-17",
      "Statement": [
        {
          "Effect": "Allow",
          "Principal": {
            "Service": "lambda.amazonaws.com"
          },
          "Action": "sts:AssumeRole"
        }
      ]
    }
  }
}
```

Next, attach the basic lambda execution role to the role.

```shell
aws iam attach-role-policy \
    --role-name lambda-execute-encord-agents \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
```

### STEP 8: Creating a lambda function
Create the Lambda function. 
For `ImageUri`, specify the repository URI from [Step 5](#step-5-prepare-ecr-container-repository). 
Make sure to include `:latest` at the end of the URI.

```shell
aws lambda create-function \
  --function-name <my-function-name> \
  --package-type Image \
  --code ImageUri=111122223333.dkr.ecr.us-east-1.amazonaws.com/<your-lambda-function-name>:latest \
  --role arn:aws:iam::061234567890:role/lambda-execute-encord-agents
```

!!! hint
    If you want to update the container image, you need to follow the above procedure again.
    Thas is, build the container ([Step 3](#step-3-build-the-docker-image)); tag and with the repository uri and upload ([Step 6](#step-6-upload-the-local-docker-image)).
    
    Then, instead of the `create-function` call in the end, you do

    ```shell
    aws lambda update-function-code \
        --function-name pdf-qa \
        --image-uri 111122223333.dkr.ecr.us-east-1.amazonaws.com/<your-lambda-function-name>:latest \
        --publish
    ```

    The URL will remain the same so no need to reconfigure CORS and all that.

Now, proceed to [Step A](#step-a-configure-public-endpoint) below to complete the setup.

## Communication with Encord

### STEP A: Configure public endpoint

Now the function is live but not publicly available to the internet.
To make it accessible to the Encord platform, follow these steps:

1. Go to [https://console.aws.amazon.com/lambda](https://console.aws.amazon.com/lambda){ target="_blank", rel="noopener noreferrer" } and navigate to your newly created function.
2. Go to the **Configuration** tab and choose the **Function URL** section.
3. Click the **Create function URL** button
4. Choose Auth type `NONE`
5. Expand the **Additional settings** panel and check the **Configure cross-origin resource sharing (CORS)** box
6. Add `https://app.encord.com`, `https://app.us.encord.com`, or your custom (VPC) domain in the **Allow origin** section
7. Add both `content-type` and `x-encord-editor-agent` values under the **Allow headers** section
8. Choose `POST` in the **Allow methods** section
9. Click **Save**

The configuration should look similar to the following image (potentially with less allowed origins).

!!! hint
    You can click the image to expand it.

![AWS Function url configuration](../assets/aws-function-url-configuration.png)

### STEP B: Adding secrets

Your agent will need an ssh key secret. In the AWS console where you configured the function url, click the **Environment variables** tab on the left.
Add the `ENCORD_SSH_KEY` variable (and any other you need, e.g., HuggingFace, OpenAI, or Gemini credentials).

!!! tip
    It is a good idea to create a service account with Encord and use an ssh key associated to that account such that you only provide access to what's actually necessary.

### STEP C: Associating the URL with Encord

Now that you have everything set up with AWS, the top of the AWS web page will display your function url. 
Copy that url and navigate over to the Encord app.

1. Click the **Agents** section on the left, and navigate to the **Editor agents** tab.
2. Click the **Register editor agent** tab 
3. Give the agent a name, (optionally) a description, and paste the function url before clicking **Register agent**

Now you can click the **Test agent** button to verify the the agent is alive and that CORS is set up correctly.
