
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

Here is the full code, but a section-by-section explanation follows.

??? "The full code for `agent.py`"
    <!--codeinclude-->
    [agent.py](../../code_examples/gcp/gcp_frame_classification.py) linenums:1
    <!--/codeinclude-->


1. Import dependencies and set up the Project.

    !!! info
        Ensure you insert your Project's unique identifier.

    <!--codeinclude-->
    [agent.py](../../code_examples/gcp/gcp_frame_classification.py) lines:1-15
    <!--/codeinclude-->

2. Create a data model and a system prompt based on the Project Ontology to tell Claude how to structure its response:

    <!--codeinclude-->
    [agent.py](../../code_examples/gcp/gcp_frame_classification.py) lines:18-29
    <!--/codeinclude-->


      ??? "See the result of `data_model.model_json_schema_str` for the given example"
          ```json
          {
            "$defs": {
              "IsThereAPersonInTheFrameRadioModel": {
                "properties": {
                  "feature_node_hash": {
                    "const": "k3EVexk7",
                    "description": "UUID for discrimination. Must be included in json as is.",
                    "enum": [
                      "k3EVexk7"
                    ],
                    "title": "Feature Node Hash",
                    "type": "string"
                  },
                  "choice": {
                    "description": "Choose exactly one answer from the given options.",
                    "discriminator": {
                      "mapping": {
                        "37rMLC/v": "#/$defs/NoNestedRadioModel",
                        "EkGwhcO4": "#/$defs/YesNestedRadioModel"
                      },
                      "propertyName": "feature_node_hash"
                    },
                    "oneOf": [
                      {
                        "$ref": "#/$defs/YesNestedRadioModel"
                      },
                      {
                        "$ref": "#/$defs/NoNestedRadioModel"
                      }
                    ],
                    "title": "Choice"
                  }
                },
                "required": [
                  "feature_node_hash",
                  "choice"
                ],
                "title": "IsThereAPersonInTheFrameRadioModel",
                "type": "object"
              },
              "NoNestedRadioModel": {
                "properties": {
                  "feature_node_hash": {
                    "const": "37rMLC/v",
                    "description": "UUID for discrimination. Must be included in json as is.",
                    "enum": [
                      "37rMLC/v"
                    ],
                    "title": "Feature Node Hash",
                    "type": "string"
                  },
                  "title": {
                    "const": "no",
                    "default": "Constant value - should be included as-is.",
                    "enum": [
                      "no"
                    ],
                    "title": "Title",
                    "type": "string"
                  }
                },
                "required": [
                  "feature_node_hash"
                ],
                "title": "NoNestedRadioModel",
                "type": "object"
              },
              "SceneSummaryTextModel": {
                "properties": {
                  "feature_node_hash": {
                    "const": "+1g9I9Sg",
                    "description": "UUID for discrimination. Must be included in json as is.",
                    "enum": [
                      "+1g9I9Sg"
                    ],
                    "title": "Feature Node Hash",
                    "type": "string"
                  },
                  "value": {
                    "description": "Please describe the image as accurate as possible focusing on 'scene summary'",
                    "maxLength": 1000,
                    "minLength": 0,
                    "title": "Value",
                    "type": "string"
                  }
                },
                "required": [
                  "feature_node_hash",
                  "value"
                ],
                "title": "SceneSummaryTextModel",
                "type": "object"
              },
              "WhatIsThePersonDoingTextModel": {
                "properties": {
                  "feature_node_hash": {
                    "const": "mj9QCDY4",
                    "description": "UUID for discrimination. Must be included in json as is.",
                    "enum": [
                      "mj9QCDY4"
                    ],
                    "title": "Feature Node Hash",
                    "type": "string"
                  },
                  "value": {
                    "description": "Please describe the image as accurate as possible focusing on 'What is the person doing?'",
                    "maxLength": 1000,
                    "minLength": 0,
                    "title": "Value",
                    "type": "string"
                  }
                },
                "required": [
                  "feature_node_hash",
                  "value"
                ],
                "title": "WhatIsThePersonDoingTextModel",
                "type": "object"
              },
              "YesNestedRadioModel": {
                "properties": {
                  "feature_node_hash": {
                    "const": "EkGwhcO4",
                    "description": "UUID for discrimination. Must be included in json as is.",
                    "enum": [
                      "EkGwhcO4"
                    ],
                    "title": "Feature Node Hash",
                    "type": "string"
                  },
                  "what_is_the_person_doing": {
                    "$ref": "#/$defs/WhatIsThePersonDoingTextModel",
                    "description": "A text attribute with carefully crafted text to describe the property."
                  }
                },
                "required": [
                  "feature_node_hash",
                  "what_is_the_person_doing"
                ],
                "title": "YesNestedRadioModel",
                "type": "object"
              }
            },
            "properties": {
              "scene_summary": {
                "$ref": "#/$defs/SceneSummaryTextModel",
                "description": "A text attribute with carefully crafted text to describe the property."
              },
              "is_there_a_person_in_the_frame": {
                "$ref": "#/$defs/IsThereAPersonInTheFrameRadioModel",
                "description": "A mutually exclusive radio attribute to choose exactly one option that best matches to the give visual input."
              }
            },
            "required": [
              "scene_summary",
              "is_there_a_person_in_the_frame"
            ],
            "title": "ClassificationModel",
            "type": "object"
          }
          ```

3. Create an Anthropic API client to communicate with Claude.

    <!--codeinclude-->
    [agent.py](../../code_examples/gcp/gcp_frame_classification.py) lines:32-33
    <!--/codeinclude-->


4. Define the editor agent.

    <!--codeinclude-->
    [agent.py](../../code_examples/gcp/gcp_frame_classification.py) lines:36-65
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

Here is the full code, but a section-by-section explanation follows.

??? "The full code for `agent.py`"
    <!--codeinclude-->

    [agent.py](../../code_examples/gcp/gcp_object_classification.py) linenums:1

    <!--/codeinclude-->

1. Create a file called `"agent.py"`. 
2. Run the following imports and read the Project Ontology. Ensure that you replace `<project_hash>` with the unique identifier of your Project.

    <!--codeinclude-->
    [agent.py](../../code_examples/gcp/gcp_object_classification.py) lines:1-14
    <!--/codeinclude-->

3. Extract the generic Ontology object and the Ontology objects that we are interested in. The following code sorts the Ontology objects based on whether they have the title `"generic"` or not.<br><br>We use the generic object to query image crops within the agent. Before doing so, we utilize `other_objects` to communicate the specific information we want Claude to focus on.<br><br>To facilitate this, the [`OntologyDataModel`](../../reference/core.md#encord_agents.core.ontology.OntologyDataModel) class helps translate Encord Ontology [`Objects`](){ target="\_blank", rel="noopener noreferrer" } into a [Pydantic](https://docs.pydantic.dev/latest/){ target="\_blank", rel="noopener noreferrer" } model, as well as convert JSON objects into Encord [`ObjectInstance`](https://docs.encord.com/sdk-documentation/sdk-references/ObjectInstance){ target="\_blank", rel="noopener noreferrer" }s.

    <!--codeinclude-->

    [agent.py](../../code_examples/gcp/gcp_object_classification.py) lines:15-19

    <!--/codeinclude-->


4. Prepare the system prompt to go along with every object crop.
For that, we use the `data_model` from above to create the json schema.
It is worth noticing that we pass in just the `other_objetcs` such that the model
is only allowed to choose between the object types that are not of the generic one.

    <!--codeinclude-->

    [agent.py](../../code_examples/gcp/gcp_object_classification.py) lines:22-30

    <!--/codeinclude-->

    ??? "See the result of `data_model.model_json_schema_str` for the given example"
        ```json
        {
          "$defs": {
            "ActivityTextModel": {
              "properties": {
                "feature_node_hash": {
                  "const": "aFCN9MMm",
                  "description": "UUID for discrimination. Must be included in json as is.",
                  "enum": [
                    "aFCN9MMm"
                  ],
                  "title": "Feature Node Hash",
                  "type": "string"
                },
                "value": {
                  "description": "Please describe the image as accurate as possible focusing on 'activity'",
                  "maxLength": 1000,
                  "minLength": 0,
                  "title": "Value",
                  "type": "string"
                }
              },
              "required": [
                "feature_node_hash",
                "value"
              ],
              "title": "ActivityTextModel",
              "type": "object"
            },
            "AnimalNestedModel": {
              "properties": {
                "feature_node_hash": {
                  "const": "3y6JxTUX",
                  "description": "UUID for discrimination. Must be included in json as is.",
                  "enum": [
                    "3y6JxTUX"
                  ],
                  "title": "Feature Node Hash",
                  "type": "string"
                },
                "type": {
                  "$ref": "#/$defs/TypeRadioModel",
                  "description": "A mutually exclusive radio attribute to choose exactly one option that best matches to the give visual input."
                },
                "description": {
                  "$ref": "#/$defs/DescriptionTextModel",
                  "description": "A text attribute with carefully crafted text to describe the property."
                }
              },
              "required": [
                "feature_node_hash",
                "type",
                "description"
              ],
              "title": "AnimalNestedModel",
              "type": "object"
            },
            "DescriptionTextModel": {
              "properties": {
                "feature_node_hash": {
                  "const": "5fFgrM+E",
                  "description": "UUID for discrimination. Must be included in json as is.",
                  "enum": [
                    "5fFgrM+E"
                  ],
                  "title": "Feature Node Hash",
                  "type": "string"
                },
                "value": {
                  "description": "Please describe the image as accurate as possible focusing on 'description'",
                  "maxLength": 1000,
                  "minLength": 0,
                  "title": "Value",
                  "type": "string"
                }
              },
              "required": [
                "feature_node_hash",
                "value"
              ],
              "title": "DescriptionTextModel",
              "type": "object"
            },
            "PersonNestedModel": {
              "properties": {
                "feature_node_hash": {
                  "const": "2xlDPPAG",
                  "description": "UUID for discrimination. Must be included in json as is.",
                  "enum": [
                    "2xlDPPAG"
                  ],
                  "title": "Feature Node Hash",
                  "type": "string"
                },
                "activity": {
                  "$ref": "#/$defs/ActivityTextModel",
                  "description": "A text attribute with carefully crafted text to describe the property."
                }
              },
              "required": [
                "feature_node_hash",
                "activity"
              ],
              "title": "PersonNestedModel",
              "type": "object"
            },
            "TypeRadioEnum": {
              "enum": [
                "dolphin",
                "monkey",
                "dog",
                "cat"
              ],
              "title": "TypeRadioEnum",
              "type": "string"
            },
            "TypeRadioModel": {
              "properties": {
                "feature_node_hash": {
                  "const": "2P7LTUZA",
                  "description": "UUID for discrimination. Must be included in json as is.",
                  "enum": [
                    "2P7LTUZA"
                  ],
                  "title": "Feature Node Hash",
                  "type": "string"
                },
                "choice": {
                  "$ref": "#/$defs/TypeRadioEnum",
                  "description": "Choose exactly one answer from the given options."
                }
              },
              "required": [
                "feature_node_hash",
                "choice"
              ],
              "title": "TypeRadioModel",
              "type": "object"
            },
            "TypeShortAndConciseTextModel": {
              "properties": {
                "feature_node_hash": {
                  "const": "79mo1G7Q",
                  "description": "UUID for discrimination. Must be included in json as is.",
                  "enum": [
                    "79mo1G7Q"
                  ],
                  "title": "Feature Node Hash",
                  "type": "string"
                },
                "value": {
                  "description": "Please describe the image as accurate as possible focusing on 'type - short and concise'",
                  "maxLength": 1000,
                  "minLength": 0,
                  "title": "Value",
                  "type": "string"
                }
              },
              "required": [
                "feature_node_hash",
                "value"
              ],
              "title": "TypeShortAndConciseTextModel",
              "type": "object"
            },
            "VehicleNestedModel": {
              "properties": {
                "feature_node_hash": {
                  "const": "llw7qdWW",
                  "description": "UUID for discrimination. Must be included in json as is.",
                  "enum": [
                    "llw7qdWW"
                  ],
                  "title": "Feature Node Hash",
                  "type": "string"
                },
                "type__short_and_concise": {
                  "$ref": "#/$defs/TypeShortAndConciseTextModel",
                  "description": "A text attribute with carefully crafted text to describe the property."
                },
                "visible": {
                  "$ref": "#/$defs/VisibleChecklistModel",
                  "description": "A collection of boolean values indicating which concepts are applicable according to the image content."
                }
              },
              "required": [
                "feature_node_hash",
                "type__short_and_concise",
                "visible"
              ],
              "title": "VehicleNestedModel",
              "type": "object"
            },
            "VisibleChecklistModel": {
              "properties": {
                "feature_node_hash": {
                  "const": "OFrk07Ds",
                  "description": "UUID for discrimination. Must be included in json as is.",
                  "enum": [
                    "OFrk07Ds"
                  ],
                  "title": "Feature Node Hash",
                  "type": "string"
                },
                "wheels": {
                  "description": "Is 'wheels' applicable or not?",
                  "title": "Wheels",
                  "type": "boolean"
                },
                "frame": {
                  "description": "Is 'frame' applicable or not?",
                  "title": "Frame",
                  "type": "boolean"
                },
                "chain": {
                  "description": "Is 'chain' applicable or not?",
                  "title": "Chain",
                  "type": "boolean"
                },
                "head_lights": {
                  "description": "Is 'head lights' applicable or not?",
                  "title": "Head Lights",
                  "type": "boolean"
                },
                "tail_lights": {
                  "description": "Is 'tail lights' applicable or not?",
                  "title": "Tail Lights",
                  "type": "boolean"
                }
              },
              "required": [
                "feature_node_hash",
                "wheels",
                "frame",
                "chain",
                "head_lights",
                "tail_lights"
              ],
              "title": "VisibleChecklistModel",
              "type": "object"
            }
          },
          "properties": {
            "choice": {
              "description": "Choose exactly one answer from the given options.",
              "discriminator": {
                "mapping": {
                  "2xlDPPAG": "#/$defs/PersonNestedModel",
                  "3y6JxTUX": "#/$defs/AnimalNestedModel",
                  "llw7qdWW": "#/$defs/VehicleNestedModel"
                },
                "propertyName": "feature_node_hash"
              },
              "oneOf": [
                {
                  "$ref": "#/$defs/PersonNestedModel"
                },
                {
                  "$ref": "#/$defs/AnimalNestedModel"
                },
                {
                  "$ref": "#/$defs/VehicleNestedModel"
                }
              ],
              "title": "Choice"
            }
          },
          "required": [
            "choice"
          ],
          "title": "ObjectsRadioModel",
          "type": "object"
        }
        ```

5. With the system prompt ready, instantiate an API client for Claude.

    <!--codeinclude-->

    [agent.py](../../code_examples/gcp/gcp_object_classification.py) lines:33-34

    <!--/codeinclude-->

6. Define the editor agent. 

    * All arguments are automatically injected when the agent is called. For details on dependency injection, see [here](../../dependencies.md).  
    * The [`dep_object_crops`](../../reference/editor_agents.md#encord_agents.gcp.dependencies.dep_object_crops) dependency allows filtering. In this case, it includes only "generic" object crops, excluding those already converted to actual labels.

    <!--codeinclude-->

    [agent.py](../../code_examples/gcp/gcp_object_classification.py) lines:38-46

    <!--/codeinclude-->


7. Call Claude using the image crops. Notice how the `crop` variable has a convenient `b64_encoding` method to produce an input that Claude understands.

  <!--codeinclude-->

  [agent.py](../../code_examples/gcp/gcp_object_classification.py) lines:47-60

  <!--/codeinclude-->

8. To parse the message from Claude, the `data_model` is again useful.
When called with a JSON string, it attempts to parse it with respect to the
the JSON schema we saw above to create an Encord object instance.
If successful, the old generic object can be removed and the newly classified object added.

    <!--codeinclude-->

    [agent.py](../../code_examples/gcp/gcp_object_classification.py) lines:63-80

    <!--/codeinclude-->

9. Save the labels with Encord.

    <!--codeinclude-->

    [agent.py](../../code_examples/gcp/gcp_object_classification.py) lines:83-84

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

## FastAPI Examples

### Basic Geometric example using objectHashes

A simple example of how you might utilise the objectHashes can be done via:

```python
from typing import Annotated

from encord.objects.ontology_labels_impl import LabelRowV2
from encord.objects.ontology_object_instance import ObjectInstance
from fastapi import Depends, FastAPI

from encord_agents.fastapi.cors import EncordCORSMiddleware
from encord_agents.fastapi.dependencies import (
    FrameData,
    dep_label_row,
    dep_objects,
)

# Initialize FastAPI app
app = FastAPI()
app.add_middleware(EncordCORSMiddleware)


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

Here is the full code, but a section-by-section explanation follows.

??? "The full code for `main.py`"
    <!--codeinclude-->
    [main.py](../../code_examples/fastapi/fastapi_frame_classification.py) linenums:1
    <!--/codeinclude-->

1. Import dependencies and set up the Project. The CORS middleware is crucial as it allows the Encord platform to make requests to your API.

    <!--codeinclude-->
    [main.py](../../code_examples/fastapi/fastapi_frame_classification.py) lines:1-22
    <!--/codeinclude-->

2. Set up the Project and create a data model based on the Ontology.

    <!--codeinclude-->
    [main.py](../../code_examples/fastapi/fastapi_frame_classification.py) lines:25-27
    <!--/codeinclude-->

3. Create the system prompt that tells Claude how to structure its response.

    <!--codeinclude-->
    [main.py](../../code_examples/fastapi/fastapi_frame_classification.py) lines:30-42
    <!--/codeinclude-->

4. Define the endpoint to handle the classification:

    <!--codeinclude-->
    [main.py](../../code_examples/fastapi/fastapi_frame_classification.py) lines:45-75
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

Here is the full code, but a section-by-section explanation follows.

??? "The full code for `main.py`"
    <!--codeinclude-->
    [main.py](../../code_examples/fastapi/fastapi_object_classification.py) linenums:1
    <!--/codeinclude-->

1. Set up the FastAPI app and CORS middleware.

    <!--codeinclude-->
    [main.py](../../code_examples/fastapi/fastapi_object_classification.py) lines:1-20
    <!--/codeinclude-->

2. Set up the client, Project, and extract the generic Ontology object.

    <!--codeinclude-->
    [main.py](../../code_examples/fastapi/fastapi_object_classification.py) lines:23-29
    <!--/codeinclude-->

3. Create the data model and system prompt for Claude.

    <!--codeinclude-->
    [main.py](../../code_examples/fastapi/fastapi_object_classification.py) lines:32-44
    <!--/codeinclude-->

4. Define the attribute endpoint:

<!--codeinclude-->
[main.py](../../code_examples/fastapi/fastapi_object_classification.py) lines:47-94
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


## Agent Examples in the Making

The following example are being worked on:

- Tightening Bounding Boxes with SAM
- Extrapolating labels with DINOv
- Triggering internal notification system
- Label assertion


