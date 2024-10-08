# Encore Agents Framework

This repository provides utility functions and examples for building both [editor agents][editor_agents] and [task agents][task_agents].
Here's how you decide which of the patterns to follow.

![Decision tree for which agent to use](graphics/decision_tree.png)

Some examples of what you could do with each type of agent:

**Editor Agent**:

- _Validate the current state of the annotations_ within a frame, video, or image group.
- Do _custom conversions_ between label types.
- _Trigger notifications_ internally related to the given task.

Think of these agents as agents that your annotators can trigger at will _while they are labeling_.

If you plan to build an editor agent, please go to the [Editor agents section](#editor-agents).

**Task Agents**:

- _Pre-labeling_ of your data, e.g., with your own model or of-the-shelf models.
- _Custom routing_ of data in the project workflow.
- _Dynamic prioritization_ of your tasks.
- _Custom "label assertions"_ that validate, e.g., number of labels or other constraings, before sending them for review.

Think of these agents as agents that will _automatically_ trigger as soon as a task reaches the associated agent state in the project workflow.

If you plan to build a label agent, please go to the [Task agents section](#task-agents).

# Installation

This repo can be installed as a slim command-line interface (CLI) to help setup and test projects and as a dependency for the implementation of an agent.

### CLI

For the CLI, we recommend installing it via [`pipx`][pipx].

```shell
pipx install https://github.com/encord-team/encord-agents.git
```

Now, you can, e.g., do `encord-agents gcp init <your_project_name>` to initialize a new python project with the
required dependencies for a GCP project.
See [GCP functions](#gcp-cloud-function-examples) below for more details.

### Dependency

There are multiple different extras that you can install - depending on how you want to setup your project.
If you are building a new FastAPI application for editor agents, you should install the project with

```
python -m pip install "encord-agents[fastapi]"
```

if you plan to use the project with GCPs `functions_framework`, then do

```
python -m pip install "encord-agents[gcp-functions]"
```

Finally, if you want to manage all the dependencies on your own, the only necessary dependencies for the `core` module
can be installed with

```
python -m pip install "encord-agents[core]"
```

### Settings

The tool will in many cases have to authenticate with Encord.
For that, environment variables are used.  
Specifically, you need to [setup an ssh key]() for a service account and use the private key to authenticate with.
For any project where you want to use your agent, you will have to assign that service account admin rights.

> 💡 Note: for testing, you can may want to use your own personal ssh-key.

To set the environment variables, you should do one of the following two:

1. Set the `ENCORD_SSH_KEY` env variable with the raw key content.
2. Set the `ENCORD_SSH_KEY_FILE` env variable with the absolute path to the key.

If none of them are set, the code will cast a pydantic validation error the first time it needs the ssh key.

> :information_source: Effectively, [this part][docs-ssh-key-access] of the `encord` SDK is used.

# Editor agents

[[📚 full docs][editor_agents]] [[👆 to the top][to_top]]

For the examples in this section, you have two choices for setups.
You can host your agent via GCP cloud functions or via a self-hosted FastAPI server.
For light-weight application like a label checks, we recommend cloud functions, while agents that employ more heavy deep learning models are more suited for a FastAPI setup.

> 💡 **Do you prefer another type of hosting?**  
> While we show you two ways in which you can host an editor agent, the options are endless.
> You need to host a public url that accepts POST requests with data of the format (sent from the Encord label editor):
>
> ```
> {
>     "projectHash": "<project_hash>",  # uuid
>     "dataHash": "<data_hash>",        # uuid
>     "frame": 0                        # int
> }
> ```
>
> and responds with a 200 status.
> Please see the [full doct][editor_agents] for more details.
>
> There are multiple "nice" utilities in the `encord_agents.core` module which might be useful in other hosting senarios.
> There is, e.g., code for extracting the right frame based on the message from the editor. # TODO make link

## GCP Cloud function examples

### Add a bounding box

This example shows how to add a bounding box to the given frame that an annotator is triggering the agent from.

```python
from encord.objects.coordinates import BoundingBoxCoordinates
from encord.objects.ontology_labels_impl import LabelRowV2

from encord_agents.gcp_functions import FrameData, editor_agent


@editor_agent()
def my_editor_agent(frame_data: FrameData, label_row: LabelRowV2) -> None:
    ins = label_row.ontology_structure.objects[0].create_instance()
    ins.set_for_frames(
        frames=frame_data.frame,
        coordinates=BoundingBoxCoordinates(
            top_left_x=0.2, top_left_y=0.2, width=0.6, height=0.6
        ),
    )
    label_row.add_object_instance(ins)
    label_row.save()
```

In the code, we:

1. We mark our function with the `@editor_agent` decorator. That will provide us with two arguments to the function.

   1. A [`FrameData`](TODO) instance which tells which `project_hash`, `data_hash`, and `frame` the agent was triggered from.
   2. A [`LabelRowV2`][label_row_v2] instance already instantiated with the current label state.

2. Create an object instance (assuming that the first object in the ontology is a bounding box object) and call `set_for_frames` with bounding box coordinates and a given frame.
3. Add the new instance to the `label_row`.
4. Save the label row.

> **Quickly replicate the example:**  
> Follow these commands from a shell with the poetry enviroinment activated.

```
git clone https://github.com/encord-team/encord-agents.git
encord-agents gcp init test-project --src-file encord-agents/examples/gcp_functions/add_bounding_box.py
cd test-project
python -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
encord-agents gcp run add_bunding_box
```

from another shell, run `encord-agents gcp test <editor_url>` where `<editor_url>` is the url you see in the browser when you are running editing an image/frame of a video.

### Testing

### Other examples

#### Call GPT-4o to varify classifications

#### Label verification

### Deployment

-- TODO ask Ali for a bit of help

</details>

### Installation

# Task agents

[[📚 full docs][task_agents]] [[👆 to the top][to_top]]

[editor_agents]: https://docs.encord.com/platform-documentation/Annotate/automated-labeling/annotate-editor-agents
[task_agents]: https://docs.encord.com/platform-documentation/Annotate/automated-labeling/annotate-task-agents
[to_top]: #encord-agents-framework
[poetry]: https://python-poetry.org/
[label_row_v2]: https://docs.encord.com/sdk-documentation/sdk-references/LabelRowV2
[pipx]: https://github.com/pypa/pipx
[docs-ssh-key-access]: https://docs.encord.com/sdk-documentation/sdk-references/EncordUserClient#create-with-ssh-private-key
