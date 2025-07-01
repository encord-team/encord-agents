
### Basic Geometric example using objectHashes

## GCP Examples
A simple example of how you might utilise the objectHashes can be done via:

```python

from typing import Annotated

from encord.objects.ontology_labels_impl import LabelRowV2
from encord.objects.ontology_object_instance import ObjectInstance

from encord_agents.core.data_model import FrameData
from encord_agents.core.dependencies import Depends
from encord_agents.gcp.dependencies import dep_objects
from encord_agents.gcp.wrappers import editor_agent


@editor_agent
def handle_object_hashes(
    frame_data: FrameData,
    lr: LabelRowV2,
    object_instances: Annotated[list[ObjectInstance], Depends(dep_objects)],
) -> None:
    for object_inst in object_instances:
        print(object_inst)

```

An example use case of the above: Suppose that I have my own OCR model and I want to selectively run OCR on objects I've selected from the Encord app. You can then trigger your agent from the app and it'll appropriately send a list of objectHashes to your agent. Then via the dep_objects method above, it gives the agent immediate access to the object instance making it easier to integrate your OCR model.

**Test the Agent**

1. Save the above code as `agent.py`.
2. Then in your current terminal, run the following command to run the agent in debug mode.

```shell
functions-framework --target=handle_object_hashes --debug --source agent.py
```

3. Open your Project in [the Encord platform](https://app.encord.com/projects){ target="_blank", rel="noopener noreferrer" } and navigate to a frame with an object that you want to act on. Choose an object from the bottom left sider and click `Copy URL` as shown:
<div align="center">
  <img src ="../../assets/examples/editor_agents/copy_url_example.png" alt="Copy URL from left sider" width="350" height="350">
</div>


!!! tip
    The url should have roughly this format: `"https://app.encord.com/label_editor/{project_hash}/{data_hash}/{frame}/0?other_query_params&objectHash={objectHash}"`.


4. In another shell operating from the same working directory, source your virtual environment and test the agent.

    ```shell
    source venv/bin/activate
    encord-agents test local agent '<your_url>'
    ```

5. To see if the test is successful, refresh your browser to see the action taken by the Agent. Once the test runs successfully, you are ready to deploy your agent. Visit [the deployment documentation](../gcp.md#step-4-deployment) to learn more.


### Nested Classification using Claude 3.5 Sonnet

The goals of this example are:

1. Create an editor agent that automatically adds frame-level classifications.
2. Demonstrate how to use the [`OntologyDataModel`](../../reference/core.md#encord_agents.core.ontology.OntologyDataModel) for classifications.

**Prerequisites**

Before you begin, ensure you have:

- Created a virtual Python environment.
- Installed all necessary dependencies.
- Have an [Anthropic API key](https://www.anthropic.com/api){ target="\_blank", rel="noopener noreferrer" }.
- Are able to [authenticate with Encord](../../authentication.md).

Run the following commands to set up your environment:

```shell
python -m venv venv                 # Create a virtual Python environment  
source venv/bin/activate            # Activate the virtual environment  
python -m pip install encord-agents anthropic  # Install required dependencies  
export ANTHROPIC_API_KEY="<your_api_key>"     # Set your Anthropic API key  
export ENCORD_SSH_KEY_FILE="/path/to/your/private/key"  # Define your Encord SSH key  

```

**Project Setup**

Create a Project with visual content (images, image groups, image sequences, or videos) in Encord. This example uses the following Ontology, but any Ontology containing classifications can be used.

![Ontology](../../assets/examples/editor_agents/gcp/ontology_preview_llm_frame_classification.png){width=300}

??? "See the ontology JSON"
    ```json title="ontology.json"
    {
      "objects": [],
      "classifications": [
        {
          "id": "1",
          "featureNodeHash": "TTkHMtuD",
          "attributes": [
            {
              "id": "1.1",
              "featureNodeHash": "+1g9I9Sg",
              "type": "text",
              "name": "scene summary",
              "required": false,
              "dynamic": false
            }
          ]
        },
        {
          "id": "2",
          "featureNodeHash": "xGV/wCD0",
          "attributes": [
            {
              "id": "2.1",
              "featureNodeHash": "k3EVexk7",
              "type": "radio",
              "name": "is there a person in the frame?",
              "required": false,
              "options": [
                {
                  "id": "2.1.1",
                  "featureNodeHash": "EkGwhcO4",
                  "label": "yes",
                  "value": "yes",
                  "options": [
                    {
                      "id": "2.1.1.1",
                      "featureNodeHash": "mj9QCDY4",
                      "type": "text",
                      "name": "What is the person doing?",
                      "required": false
                    }
                  ]
                },
                {
                  "id": "2.1.2",
                  "featureNodeHash": "37rMLC/v",
                  "label": "no",
                  "value": "no",
                  "options": []
                }
              ],
              "dynamic": false
            }
          ]
        }
      ]
    }
    ```

    To construct the same Ontology as used in this example, run the following script.

    ```python
    import json
    from encord.objects.ontology_structure import OntologyStructure
    from encord_agents.core.utils import get_user_client

    encord_client = get_user_client()
    structure = OntologyStructure.from_dict(json.loads("{the_json_above}"))
    ontology = encord_client.create_ontology(
        title="Your ontology title",
        structure=structure
    )
    print(ontology.ontology_hash)
    ```

The aim is to trigger an agent that transforms a labeling task from Figure A to Figure B. *(Hint: Click the images and use the keyboard arrows to toggle between them.)*

<div style="display: flex; justify-content: space-between; gap: 1em;">
    <figure style="text-align: center; flex: 1; margin: 1em 0;">
      <img src="../../assets/examples/editor_agents/gcp/frame_classification_generic.png" width="100%"/>
      <strong>Figure A:</strong> No classification labels.
    </figure>
    <figure style="text-align: center; flex: 1; margin: 1em 0;">
      <img src="../../assets/examples/editor_agents/gcp/frame_classification_filled.png" width="100%"/>
      <strong>Figure B:</strong> Multiple nested classification labels generated by an LLM.
    </figure>
</div>

**Create the Agent**

Here is the full code.

??? "The full code for `agent.py`"
    <!--codeinclude-->
    [agent.py](../../code_examples/gcp/gcp_frame_classification.py) linenums:1
    <!--/codeinclude-->

The agent follows these steps:  

1. Automatically retrieves the frame content using the `dep_single_frame` dependency.  
2. Sends the frame image to Claude for analysis.  
3. Parses Claude's response into classification instances using the predefined data model.  
4. Adds the classifications to the label row and saves the results.

**Test the Agent**

1. In your current terminal, run the following command to run the agent in debug mode.

    ```shell
    functions-framework --target=agent --debug --source agent.py
    ```

2. Open your Project in [the Encord platform](https://app.encord.com/projects){ target="_blank", rel="noopener noreferrer" } and navigate to a frame you want to add a classification to. Copy the URL from your browser.

    !!! tip
        The url should have roughly this format: `"https://app.encord.com/label_editor/{project_hash}/{data_hash}/{frame}"`.


3. In another shell operating from the same working directory, source your virtual environment and test the agent.

    ```shell
    source venv/bin/activate
    encord-agents test local agent '<your_url>'
    ```

4. To see if the test is successful, refresh your browser to view the classifications generated by Claude. Once the test runs successfully, you are ready to deploy your agent. Visit [the deployment documentation](../gcp.md#step-4-deployment) to learn more.

### Nested Attributes using Claude 3.5 Sonnet

The goals of this example are:

1. Create an editor agent that can convert generic object annotations (class-less coordinates) into class specific annotations with nested attributes like descriptions, radio buttons, and checklists.
2. Demonstrate how to use both the [`OntologyDataModel`](../../reference/core.md#encord_agents.core.ontology.OntologyDataModel) and the [`dep_object_crops`](../../reference/editor_agents.md#encord_agents.gcp.dependencies.dep_object_crops) dependency.

**Prerequisites**

Before you begin, ensure you have:

- Created a virtual Python environment.
- Installed all necessary dependencies.
- Have an [Anthropic API key](https://www.anthropic.com/api){ target="\_blank", rel="noopener noreferrer" }.
- Are able to [authenticate with Encord](../../authentication.md).

Run the following commands to set up your environment:

```shell
python -m venv venv                 # Create a virtual Python environment  
source venv/bin/activate            # Activate the virtual environment  
python -m pip install encord-agents anthropic  # Install required dependencies  
export ANTHROPIC_API_KEY="<your_api_key>"     # Set your Anthropic API key  
export ENCORD_SSH_KEY_FILE="/path/to/your/private/key"  # Define your Encord SSH key  

```

**Project Setup**

Create a Project with visual content (images, image groups, image sequences, or videos) in Encord. This example uses the following Ontology, but any Ontology containing classifications can be used provided the object types are the same and there is one entry called `"generic"`.

![Ontology](../../assets/examples/editor_agents/gcp/ontology_preview_llm_classification.png){width=300}

??? "See the ontology JSON"
    ```json title="ontology.json"
    {
      "objects": [
        {
          "id": "1",
          "name": "person",
          "color": "#D33115",
          "shape": "bounding_box",
          "featureNodeHash": "2xlDPPAG",
          "required": false,
          "attributes": [
            {
              "id": "1.1",
              "featureNodeHash": "aFCN9MMm",
              "type": "text",
              "name": "activity",
              "required": false,
              "dynamic": false
            }
          ]
        },
        {
          "id": "2",
          "name": "animal",
          "color": "#E27300",
          "shape": "bounding_box",
          "featureNodeHash": "3y6JxTUX",
          "required": false,
          "attributes": [
            {
              "id": "2.1",
              "featureNodeHash": "2P7LTUZA",
              "type": "radio",
              "name": "type",
              "required": false,
              "options": [
                {
                  "id": "2.1.1",
                  "featureNodeHash": "gJvcEeLl",
                  "label": "dolphin",
                  "value": "dolphin",
                  "options": []
                },
                {
                  "id": "2.1.2",
                  "featureNodeHash": "CxrftGS4",
                  "label": "monkey",
                  "value": "monkey",
                  "options": []
                },
                {
                  "id": "2.1.3",
                  "featureNodeHash": "OQyWm7Sm",
                  "label": "dog",
                  "value": "dog",
                  "options": []
                },
                {
                  "id": "2.1.4",
                  "featureNodeHash": "CDKmYJK/",
                  "label": "cat",
                  "value": "cat",
                  "options": []
                }
              ],
              "dynamic": false
            },
            {
              "id": "2.2",
              "featureNodeHash": "5fFgrM+E",
              "type": "text",
              "name": "description",
              "required": false,
              "dynamic": false
            }
          ]
        },
        {
          "id": "3",
          "name": "vehicle",
          "color": "#16406C",
          "shape": "bounding_box",
          "featureNodeHash": "llw7qdWW",
          "required": false,
          "attributes": [
            {
              "id": "3.1",
              "featureNodeHash": "79mo1G7Q",
              "type": "text",
              "name": "type - short and concise",
              "required": false,
              "dynamic": false
            },
            {
              "id": "3.2",
              "featureNodeHash": "OFrk07Ds",
              "type": "checklist",
              "name": "visible",
              "required": false,
              "options": [
                {
                  "id": "3.2.1",
                  "featureNodeHash": "KmX/HjRT",
                  "label": "wheels",
                  "value": "wheels"
                },
                {
                  "id": "3.2.2",
                  "featureNodeHash": "H6qbEcdj",
                  "label": "frame",
                  "value": "frame"
                },
                {
                  "id": "3.2.3",
                  "featureNodeHash": "gZ9OucoQ",
                  "label": "chain",
                  "value": "chain"
                },
                {
                  "id": "3.2.4",
                  "featureNodeHash": "cit3aZSz",
                  "label": "head lights",
                  "value": "head_lights"
                },
                {
                  "id": "3.2.5",
                  "featureNodeHash": "qQ3PieJ/",
                  "label": "tail lights",
                  "value": "tail_lights"
                }
              ],
              "dynamic": false
            }
          ]
        },
        {
          "id": "4",
          "name": "generic",
          "color": "#FE9200",
          "shape": "bounding_box",
          "featureNodeHash": "jootTFfQ",
          "required": false,
          "attributes": []
        }
      ],
      "classifications": []
    }
    `

    To construct the Ontology used in this example, run the following script:

    ```python
    import json
    from encord.objects.ontology_structure import OntologyStructure
    from encord_agents.core.utils import get_user_client

    encord_client = get_user_client()
    structure = OntologyStructure.from_dict(json.loads("{the_json_above}"))
    ontology = encord_client.create_ontology(
        title="Your ontology title",
        structure=structure
    )
    print(ontology.ontology_hash)
    ```

The goal is create an agent that takes a labeling task from Figure A to Figure B, below (*Hint*: you can click them and use keyboard arrows toggle between images).

<div style="display: flex; justify-content: space-between; gap: 1em;">
    <figure style="text-align: center; flex: 1; margin: 1em 0;">
      <img src="../../assets/examples/editor_agents/gcp/object_classification_generic.png" width="100%"/>
      <strong>Figure A:</strong> A generic label without any type annotations. Notice that in the left sidebar, there are two "generic" labels.
    </figure>
    <figure style="text-align: center; flex: 1; margin: 1em 0;">
      <img src="../../assets/examples/editor_agents/gcp/object_classification_filled.png" width="100%"/>
      <strong>Figure B:</strong> A nested label with all details filled for the predicted class. Notice that in the left sidebar, there are two "animal" labels with both type and description filled.
    </figure>
</div>

**Create the Agent**

!!! warning
    Some code blocks in this section have incorrect indentation. If you plan to copy and paste, we **strongly** recommend using the full code below instead of the individual sub-sections.

Here is the full code.

??? "The full code for `agent.py`"
    <!--codeinclude-->
    [agent.py](../../code_examples/gcp/gcp_object_classification.py) linenums:1
    <!--/codeinclude-->

**Test the Agent**

1. In your current terminal, run the following command to run the agent in debug mode.

    ```shell
    functions-framework --target=agent --debug --source agent.py
    ```

2. Open your Project in the Encord platform and navigate to a frame you want to add a generic object to. Copy the URL from your browser.

    !!! hint
        The url should have the following format: `"https://app.encord.com/label_editor/{project_hash}/{data_hash}/{frame}"`.

3. In another shell operating from the same working directory, source your virtual environment and test the agent.

    ```shell
    source venv/bin/activate
    encord-agents test local agent <your_url>
    ```

4. To see if the test is successful, refresh your browser to view the classifications generated by Claude. Once the test runs successfully, you are ready to deploy your agent. Visit the deployment documentation to learn more.

### Video Recaptioning using GPT-4o-mini

The goals of this example are:

1. Create an editor agent that automatically generates multiple variations of video captions.
2. Demonstrate how to use OpenAI's GPT-4o-mini model to enhance human-created video captions.

**Prerequisites**

Before you begin, ensure you have:

- Created a virtual Python environment.
- Installed all necessary dependencies.
- Have an [OpenAI API key](https://platform.openai.com/api-keys){ target="\_blank", rel="noopener noreferrer" }.
- Are able to [authenticate with Encord](../../authentication.md).

Run the following commands to set up your environment:

```shell
python -m venv venv                 # Create a virtual Python environment  
source venv/bin/activate            # Activate the virtual environment  
python -m pip install encord-agents langchain-openai functions-framework openai  # Install required dependencies  
export OPENAI_API_KEY="<your-api-key>"     # Set your OpenAI API key  
export ENCORD_SSH_KEY_FILE="/path/to/your/private/key"  # Define your Encord SSH key  
```

**Project Setup**

Create a Project with video content in Encord. 

This example requires an ontology with four text classifications as demonstrated in the figure below:

* 1) A text classification for human-created summaries of what's happening in the video.
* 2-4) Three text classifications that will be automatically filled by the LLM.

<figure style="text-align: center; justify-items: center; flex: 1; margin: 1em 0; width: 100%;">
  <img src="/assets/examples/editor_agents/recaptioning_ontology.png" width="200"/>
  <strong>Ontology</strong> 
</figure>

??? "Expand to see ontology JSON"
    ```json
    {
      "objects": [],
      "classifications": [
        {
          "id": "1",
          "featureNodeHash": "GCH8VHIK",
          "attributes": [
            {
              "id": "1.1",
              "name": "Caption",
              "type": "text",
              "required": false,
              "featureNodeHash": "Yg7xXEfC"
            }
          ]
        },
        {
          "id": "2",
          "featureNodeHash": "PwQAwYid",
          "attributes": [
            {
              "id": "2.1",
              "name": "Caption Rephrased 1",
              "type": "text",
              "required": false,
              "featureNodeHash": "aQdXJwbG"
            }
          ]
        },
        {
          "id": "3",
          "featureNodeHash": "3a/aSnHO",
          "attributes": [
            {
              "id": "3.1",
              "name": "Caption Rephrased 2",
              "type": "text",
              "required": false,
              "featureNodeHash": "8zY6H62x"
            }
          ]
        },
        {
          "id": "4",
          "featureNodeHash": "FNjXp5TU",
          "attributes": [
            {
              "id": "4.1",
              "name": "Caption Rephrased 3",
              "type": "text",
              "required": false,
              "featureNodeHash": "sKg1Kq/m"
            }
          ]
        }
      ]
    }
    ```


??? "Code for generating a compatible ontology"
    ```python
    import json
    from encord.objects.ontology_structure import OntologyStructure
    from encord.objects.attributes import TextAttribute

    structure = OntologyStructure()
    caption = structure.add_classification()
    caption.add_attribute(TextAttribute, "Caption")
    re1 = structure.add_classification()
    re1.add_attribute(TextAttribute, "Recaption 1")
    re2 = structure.add_classification()
    re2.add_attribute(TextAttribute, "Recaption 2")
    re3 = structure.add_classification()
    re3.add_attribute(TextAttribute, "Recaption 3")

    print(json.dumps(structure.to_dict(), indent=2))

    create_ontology = False
    if create_ontology:
        from encord.user_client import EncordUserClient
        client = EncordUserClient.create_with_ssh_private_key()  # Look in auth section for authentication
        client.create_ontology("title", "description", structure)
    ```


As the figure below depicts, the workflow for this agent is:

1. A human views the video and enters a caption in the first text field.
2. The agent is triggered, which fills the three other caption fields with variations for the human to review and potentially correct.

Every video is being annotated with a caption by a human (the pink node).
Successively, a data agent produces multiple new captions automatically (the purple node).
Finally, a humans reviews all four captions (the yellow node) before the item is complete.
If there are no human captions when the task reaches the data agent, it sends it back for annotation.
Similarly, if the task is rejected during review, it is also sent back for another round of annotation.

<figure style="text-align: center; flex: 1; margin: 1em 0;">
  <img src="/assets/examples/editor_agents/recaptioning_workflow.png" width="100%"/>
  <strong>Workflow</strong> 
</figure>


**Create the Agent**

Here is the full code.

??? "The full code for `main.py`"
    <!--codeinclude-->
    [main.py](../../code_examples/gcp/gcp_recaption_video.py) linenums:1
    <!--/codeinclude-->

The agent follows these steps:

1. It retrieves the existing human-created caption, prioritizing captions from the current frame or falling back to frame zero.
2. It sends the first frame of the video along with the human caption to the LLM.
3. It processes the LLM's response, which contains three different rephrasings of the original caption.
4. It updates the label row with the new captions, replacing any existing ones.

**Test the Agent**

1. In your current terminal, run the following command to run the agent in debug mode:

    ```shell
    ENCORD_SSH_KEY_FILE=/path/to/your_private_key \
    OPENAI_API_KEY=<your-api-key> \
    functions-framework --target=my_agent --debug --source main.py
    ```

2. Open your Project in the Encord platform, navigate to a video frame, and add your initial caption. Copy the URL from your browser.

3. In another shell operating from the same working directory, source your virtual environment and test the agent:

    ```shell
    source venv/bin/activate
    encord-agents test local my_agent '<your_url>'
    ```

4. Refresh your browser to view the three AI-generated caption variations. Once the test runs successfully, you are ready to deploy your agent. Visit [the deployment documentation](../gcp.md#step-4-deployment) to learn more.

## FastAPI Examples

### Basic Geometric example using objectHashes

A simple example of how you might utilise the objectHashes can be done via:

```python
from typing import Annotated

from encord.objects.ontology_labels_impl import LabelRowV2
from encord.objects.ontology_object_instance import ObjectInstance
from fastapi import Depends, FastAPI

from encord_agents.fastapi.cors import get_encord_app()
from encord_agents.fastapi.dependencies import (
    FrameData,
    dep_label_row,
    dep_objects,
)

# Initialize FastAPI app
app = get_encord_app()


@app.post("/handle-object-hashes")
def handle_object_hashes(
    frame_data: FrameData,
    lr: Annotated[LabelRowV2, Depends(dep_label_row)],
    object_instances: Annotated[list[ObjectInstance], Depends(dep_objects)],
) -> None:
    for object_inst in object_instances:
        print(object_inst)
```

An example use case of the above: Suppose that I have my own OCR model and I want to selectively run OCR on objects I've selected from the Encord app. You can then trigger your agent from the app and it'll appropriately send a list of objectHashes to your agent. Then via the dep_objects method above, it gives the agent immediate access to the object instance making it easier to integrate your OCR model.

<!-- TODO: Could we make a better example -->

**Test the Agent**

1. First save the above code as main.py then in your current terminal run the following command to runFastAPI server in development mode with auto-reload enabled.

    ```shell
    uvicorn main:app --reload --port 8080
    ```

2. Open your Project in [the Encord platform](https://app.encord.com/projects){ target="_blank", rel="noopener noreferrer" } and navigate to a frame with an object that you want to act on. Choose an object from the bottom left sider and click `Copy URL` as shown:
<div align="center">
  <img src ="../../assets/examples/editor_agents/copy_url_example.png" alt="Copy URL from left sider" width="350" height="350">
</div>


  !!! tip
      The url should have roughly this format: `"https://app.encord.com/label_editor/{project_hash}/{data_hash}/{frame}/0?other_query_params&objectHash={objectHash}"`.


3. In another shell operating from the same working directory, source your virtual environment and test the agent.

    ```shell
    source venv/bin/activate
    encord-agents test local agent '<your_url>'
    ```

4. To see if the test is successful, refresh your browser to see the action taken by the Agent. Once the test runs successfully, you are ready to deploy your agent. Visit [the deployment documentation](../gcp.md#step-4-deployment) to learn more.
### Nested Classification using Claude 3.5 Sonnet

The goals of this example is to:

1. Create an editor agent that can automatically fill in frame-level classifications in the Label Editor.
2. Demonstrate how to use the [`OntologyDataModel`](../../reference/core.md#encord_agents.core.ontology.OntologyDataModel) for classifications.
3. Demonstrate how to build an agent using FastAPI that can be self-hosted.

**Prerequisites**

Before you begin, ensure you have:

- Created a virtual Python environment.
- Installed all necessary dependencies.
- Have an [Anthropic API key](https://www.anthropic.com/api){ target="\_blank", rel="noopener noreferrer" }.
- Are able to [authenticate with Encord](../../authentication.md).

Run the following commands to set up your environment:

```shell
python -m venv venv                   # Create a virtual Python environment  
source venv/bin/activate              # Activate the virtual environment 
python -m pip install "fastapi[standard]" encord-agents anthropic # Install required dependencies  
export ANTHROPIC_API_KEY="<your_api_key>" # Set your Anthropic API key 
export ENCORD_SSH_KEY_FILE="/path/to/your/private/key"  # Define your Encord SSH key 
```

**Project Setup**

Create a Project with visual content (images, image groups, image sequences, or videos) in Encord. This example uses the following Ontology, but any Ontology containing classifications can be used.

![Ontology](../../assets/examples/editor_agents/gcp/ontology_preview_llm_frame_classification.png){width=300}

??? "See the ontology JSON"
    [Same JSON as in GCP Frame Classification example]

The aim is to trigger an agent that transforms a labeling task from Figure A to Figure B. *(Hint: Click the images and use the keyboard arrows to toggle between them.)*

<div style="display: flex; justify-content: space-between; gap: 1em;">
    <figure style="text-align: center; flex: 1; margin: 1em 0;">
      <img src="../../assets/examples/editor_agents/gcp/frame_classification_generic.png" width="100%"/>
      <strong>Figure A:</strong> no classification labels.
    </figure>
    <figure style="text-align: center; flex: 1; margin: 1em 0;">
      <img src="../../assets/examples/editor_agents/gcp/frame_classification_filled.png" width="100%"/>
      <strong>Figure B:</strong> Multiple nested labels coming from an LLM.
    </figure>
</div>

**Create the FastAPI agent**

Here is the full code.

??? "The full code for `main.py`"
    <!--codeinclude-->
    [main.py](../../code_examples/fastapi/fastapi_frame_classification.py) linenums:1
    <!--/codeinclude-->

The endpoint:  

1. Receives frame data via FastAPI's Form dependency.  
2. Retrieves the label row and frame content using Encord agents' dependencies.  
3. Constructs a `Frame` object with the content.  
4. Sends the frame image to Claude for analysis.  
5. Parses Claude's response into classification instances.  
6. Adds classifications to the label row and saves the updated data.

**Test the Agent**

1. In your current terminal run the following command to runFastAPI server in development mode with auto-reload enabled.

    ```shell
    uvicorn main:app --reload --port 8080
    ```

2. Open your Project in the Encord platform and navigate to a frame you want to add a classification to. Copy the URL from your browser.

    !!! tip
        The url should have the following format: `"https://app.encord.com/label_editor/{project_hash}/{data_hash}/{frame}"`.


3. In another shell operating from the same working directory, source your virtual environment and test the agent.

    ```shell
    source venv/bin/activate
    encord-agents test local frame_classification '<your_url>'
    ```

4. To see if the test is successful, refresh your browser to view the classifications generated by Claude. Once the test runs successfully, you are ready to deploy your agent. Visit the deployment documentation to learn more.

### Nested Attributes using Claude 3.5 Sonnet

The goals of this example are:

1. Create an editor agent that can convert generic object annotations (class-less coordinates) into class specific annotations with nested attributes like descriptions, radio buttons, and checklists.
2. Demonstrate how to use both the [`OntologyDataModel`](../../reference/core.md#encord_agents.core.ontology.OntologyDataModel) and the [`dep_object_crops`](../../reference/editor_agents.md#encord_agents.gcp.dependencies.dep_object_crops) dependency.

**Prerequisites**

Before you begin, ensure you have:

- Created a virtual Python environment.
- Installed all necessary dependencies.
- Have an [Anthropic API key](https://www.anthropic.com/api){ target="\_blank", rel="noopener noreferrer" }.
- Are able to [authenticate with Encord](../../authentication.md).

Run the following commands to set up your environment:

```shell
python -m venv venv                 # Create a virtual Python environment  
source venv/bin/activate            # Activate the virtual environment  
python -m pip install encord-agents anthropic  # Install required dependencies  
export ANTHROPIC_API_KEY="<your_api_key>"     # Set your Anthropic API key  
export ENCORD_SSH_KEY_FILE="/path/to/your/private/key"  # Define your Encord SSH key  

```

**Project Setup**

Create a Project with visual content (images, image groups, image sequences, or videos) in Encord. This example uses the following Ontology, but any Ontology containing classifications can be used provided the object types are the same and there is one entry called "generic".

![Ontology](../../assets/examples/editor_agents/gcp/ontology_preview_llm_classification.png){width=300}

??? "See the ontology JSON"
    [Same JSON as in GCP Object Classification example]

The goal is to trigger an agent that takes a labeling task from Figure A to Figure B, below:

<div style="display: flex; justify-content: space-between; gap: 1em;">
    <figure style="text-align: center; flex: 1; margin: 1em 0;">
      <img src="../../assets/examples/editor_agents/gcp/object_classification_generic.png" width="100%"/>
      <strong>Figure A:</strong> A generic label without any type annotations.
    </figure>
    <figure style="text-align: center; flex: 1; margin: 1em 0;">
      <img src="../../assets/examples/editor_agents/gcp/object_classification_filled.png" width="100%"/>
      <strong>Figure B:</strong> A nested label with all details filled for the predicted class.
    </figure>
</div>

**Create the FastAPI Agent**

Here is the full code.

??? "The full code for `main.py`"
    <!--codeinclude-->
    [main.py](../../code_examples/fastapi/fastapi_object_classification.py) linenums:1
    <!--/codeinclude-->

The endpoint:

1. Receives frame data using FastAPI's Form dependency.  
2. Retrieves the label row using `dep_label_row`.  
3. Fetches object crops, filtered to include only "generic" objects, using `dep_object_crops`.  
4. For each crop:  
    1. Sends the cropped image to Claude for analysis.  
    2. Parses the response into an object instance.  
    3. Replaces the generic object with the classified instance.  
5. Saves the updated label row.

**Testing the Agent**

1. In your current terminal run the following command to runFastAPI server in development mode with auto-reload enabled.

    ```shell
    fastapi dev agent.py --port 8080
    ```

2. Open your Project in the Encord platform and navigate to a frame you want to add a classification to. Copy the URL from your browser.

    !!! tip
        The url should have roughly this format: `"https://app.encord.com/label_editor/{project_hash}/{data_hash}/{frame}"`.


3. In another shell operating from the same working directory, source your virtual environment and test the agent:

    ```shell
    source venv/bin/activate
    encord-agents test local object_classification '<your_url>'
    ```

4. To see if the test is successful, refresh your browser to view the classifications generated by Claude. Once the test runs successfully, you are ready to deploy your agent. Visit the deployment documentation to learn more.


### Video Recaptioning using GPT-4o-mini

The goals of this example are:

1. Create an editor agent that automatically generates multiple variations of video captions.
2. Demonstrate how to use OpenAI's GPT-4o-mini model to enhance human-created video captions with a FastAPI-based agent.

**Prerequisites**

Before you begin, ensure you have:

- Created a virtual Python environment.
- Installed all necessary dependencies.
- Have an [OpenAI API key](https://platform.openai.com/api-keys){ target="\_blank", rel="noopener noreferrer" }.
- Are able to [authenticate with Encord](../../authentication.md).

Run the following commands to set up your environment:

```shell
python -m venv venv                 # Create a virtual Python environment  
source venv/bin/activate            # Activate the virtual environment  
python -m pip install encord-agents langchain-openai "fastapi[standard]" openai  # Install required dependencies  
export OPENAI_API_KEY="<your-api-key>"     # Set your OpenAI API key  
export ENCORD_SSH_KEY_FILE="/path/to/your/private/key"  # Define your Encord SSH key  
```

**Project Setup**

Create a Project with video content in Encord. 

This example requires an Ontology with four text classifications:

* 1) A text classification for human-created summaries of what is happening in the video.
* 2-4) Three text classifications that will be automatically filled by the LLM.

<figure style="text-align: center; justify-items: center; flex: 1; margin: 1em 0; width: 100%;">
  <img src="/assets/examples/editor_agents/recaptioning_ontology.png" width="200"/>
  <strong>Ontology</strong> 
</figure>

??? "Expand to see the Ontology JSON"
    ```json
    {
      "objects": [],
      "classifications": [
        {
          "id": "1",
          "featureNodeHash": "GCH8VHIK",
          "attributes": [
            {
              "id": "1.1",
              "name": "Caption",
              "type": "text",
              "required": false,
              "featureNodeHash": "Yg7xXEfC"
            }
          ]
        },
        {
          "id": "2",
          "featureNodeHash": "PwQAwYid",
          "attributes": [
            {
              "id": "2.1",
              "name": "Caption Rephrased 1",
              "type": "text",
              "required": false,
              "featureNodeHash": "aQdXJwbG"
            }
          ]
        },
        {
          "id": "3",
          "featureNodeHash": "3a/aSnHO",
          "attributes": [
            {
              "id": "3.1",
              "name": "Caption Rephrased 2",
              "type": "text",
              "required": false,
              "featureNodeHash": "8zY6H62x"
            }
          ]
        },
        {
          "id": "4",
          "featureNodeHash": "FNjXp5TU",
          "attributes": [
            {
              "id": "4.1",
              "name": "Caption Rephrased 3",
              "type": "text",
              "required": false,
              "featureNodeHash": "sKg1Kq/m"
            }
          ]
        }
      ]
    }
    ```


??? "Code for generating a compatible ontology"
    ```python
    import json
    from encord.objects.ontology_structure import OntologyStructure
    from encord.objects.attributes import TextAttribute

    structure = OntologyStructure()
    caption = structure.add_classification()
    caption.add_attribute(TextAttribute, "Caption")
    re1 = structure.add_classification()
    re1.add_attribute(TextAttribute, "Recaption 1")
    re2 = structure.add_classification()
    re2.add_attribute(TextAttribute, "Recaption 2")
    re3 = structure.add_classification()
    re3.add_attribute(TextAttribute, "Recaption 3")

    print(json.dumps(structure.to_dict(), indent=2))

    create_ontology = False
    if create_ontology:
        from encord.user_client import EncordUserClient
        client = EncordUserClient.create_with_ssh_private_key()  # Look in auth section for authentication
        client.create_ontology("title", "description", structure)
    ```


As the figure below depicts, the workflow for this agent is:

1. A human views the video and enters a caption in the first text field.
2. The agent is triggered, which fills the three other caption fields with variations for the human to review and potentially correct.

Every video is being annotated with a caption by a human (the pink node).
Successively, a data agent produces multiple new captions automatically (the purple node).
Finally, a humans reviews all four captions (the yellow node) before the item is complete.
If there are no human captions when the task reaches the data agent, sends it back for annotation.
Similarly, if the task is rejected during review, it is also sent back for another round of annotation.

<figure style="text-align: center; flex: 1; margin: 1em 0;">
  <img src="/assets/examples/editor_agents/recaptioning_workflow.png" width="100%"/>
  <strong>Workflow</strong> 
</figure>

**Create the Agent**

Here is the full code.

??? "The full code for `main.py`"
    <!--codeinclude-->
    [main.py](../../code_examples/fastapi/fastapi_recaption_video.py) linenums:1
    <!--/codeinclude-->

The endpoint follows these steps:

1. It retrieves the existing human-created caption, prioritizing captions from the current frame or falling back to frame zero.
2. It sends the first frame of the video along with the human caption to the LLM.
3. It processes the LLM's response, which contains three different rephrasings of the original caption.
4. It updates the label row with the new captions, replacing any existing ones.

**Test the Agent**

1. In your current terminal, run the following command to run the FastAPI server:

    ```shell
    ENCORD_SSH_KEY_FILE=/path/to/your_private_key \
    OPENAI_API_KEY=<your-api-key> \
    fastapi dev main.py
    ```

2. Open your Project in the Encord platform, navigate to a video frame, and add your initial caption. Copy the URL from your browser.

3. In another shell operating from the same working directory, source your virtual environment and test the agent:

    ```shell
    source venv/bin/activate
    encord-agents test local my_agent '<your_url>'
    ```

4. Refresh your browser to view the three AI-generated caption variations. Once the test runs successfully, you are ready to deploy your agent. Visit [the deployment documentation](../fastapi.md) to learn more.


## Modal Example

### Cotracker3 Keypoint tracking

[Cotracker3](https://cotracker3.github.io/){ target="\_blank", rel="noopener noreferrer" } is a keypoint tracking algorithm from Meta that serves as an excellent example of Modal agents. Cotracker3 involves a moderately sized (100MB) model where deployment on Modal and access to a serverless GPU works excellently.

**Prerequisites**

Firstly, we would strongly encourage any reader to first read and follow the general [Modal tutorial](../modal.md). This provides clear instructions on how to register your Encord credentials in the Modal platform and more straight forward agent code.
One new dependency here is that we need to pull in the model weights and have additional ML dependencies.
Additionally, create a Python venv with:

  ```shell
  python -m venv venv
  source venv/bin/activate
  python -m pip install encord-agents modal
  ```

as in the original modal tutorial.

Additionally to bring in the cotracker dependency, we found the most straightforward way to be:

  ```shell
  git clone https://github.com/facebookresearch/co-tracker.git
  mv co-tracker/cotracker ./cotracker
  ```

**Create the Modal Agent**

Here is the full code.

??? "The full code for `main.py`"
    <!--codeinclude-->
    [main.py](../../code_examples/modal/editor_cotracker3.py) linenums:1
    <!--/codeinclude-->

**Create the Modal Agent**

Once the above (full) code has been saved at `app.py` say, it can be deployed with: `modal deploy app.py`. Please note that it is written to use an L4 GPU so there will be some usage charges but this model can easily be used and tested within Modal's $5 free allowance.

This agent then utilises the tracking prompted on agents so to trigger, please right-click on a keypoint in the platform and trigger with this agent.

## Agent Examples in the Making

The following example are being worked on:

- Tightening Bounding Boxes with SAM
- Extrapolating labels with DINOv
- Triggering internal notification system
- Label assertion


