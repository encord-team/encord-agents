## Transferring labels to a twin project

This example shows how to take checklist labels annotated in "Project A" and translate them into yes/no radio labels in "Project B".

Assume you have an ontology like this one in Project A:

![](../../assets/examples/tasks_agents/twin_classification_transfer_source_ontology.png){width=600}

and you want to ensure that everytime a task in Project A is compelte, it gets translated to a "model friendly version" with radio classifications in Project B.
A good way to do it is make an agent do the translation to the ontology of Project B:

![](../../assets/examples/tasks_agents/twin_classification_transfer_sink_ontology.png){width=600}

> Notice how there are now three classifications (with the exact same names!) with two options each.

To build an agent that automatically translates between the two, the [`dep_twin_label_row` dependency](../../reference/task_agents.md#encord_agents.tasks.dependencies.dep_twin_label_row) is a good place to start.
For every label row from Project A that the agent is called with, it will automatically get the corresponding label row (and potentially workflow task) from project B.

> **Disclaimer:** Project A and Project B must be attached to the same datasets.

The code that defined such an agent can look similar to this:

<!--codeinclude-->
[](../../code_examples/tasks/twin_project.py)
<!--/codeinclude-->

For this code to work, the project workflows could look like this:

<figure style="text-align: center">
  <img src="../../assets/examples/tasks_agents/twin_classification_transfer_source_workflow.png" width="100%"/>
  The workflow of Project A.
</figure>

<figure style="text-align: center">
  <img src="../../assets/examples/tasks_agents/twin_classification_transfer_sink_workflow.png" width= "100%" />
  The workflow of Project B.
</figure>

With this setup, all the manual work happens in Project A and Project B just becomes a mirror
with transformed labels.

Which would mean that the agents would be defined with the following decorator to
make the workflow stage association explicit.

```python
from uuid import UUID
@runner.stage(stage=UUID("60d9f14f-755e-40fd-..."))  # <- last bit omitted
```

> Notice the match between the uuid in the "label transfer" agent stage of the workflow in Project A and the UUID in the decorator.

**To prepare your projects:**

Create two projects, one with each of the (classification) ontologies and workflows displayed above.
For this particular example, it is not important which checklists the ontologies have as long as their names match between the two ontologies.
Make sure that both projects are pointing to the same dataset(s).

**To run the agent, follow these steps:**

1. Ensure that you've exported your private key, as described in the [authentication section](../../authentication.md){target=\_blank}, and that you've [installed](../../installation.md){target=\_blank} the `encord_agents` package.
2. Update the code to capture your own project hashes. (replace `<project_hash_a>` and `<project_hash_b>`.
3. Update the `stage` argument to the decorator to reflect the uuid of your actual agent stage.
4. Update the completion pathway uuids
5. Run the file: `python twin_project.py`

Now you should see tasks that have been approved by review starting to move to the Complete state and labels starting to show up

## Examples that we're working on

- Pre-labeling with YoloWorld
- Transcribing with Whisper
- Routing with Gemini
- Prioritizing with GPT-4o mini
- Evaluating Training projects
- Transferring labels upon completion
- HF Image segmentation API
- HF LLM API to classify frames

```

```
