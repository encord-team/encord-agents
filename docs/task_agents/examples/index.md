## Prioritizing Tasks Based on File Names

This example demonstrates how to set up an agent node early in a Workflow to automatically assign a [priority](https://docs.encord.com/platform-documentation/Annotate/annotate-projects/annotate-manage-annotation-projects#task-priority) to each task before advancing it to the annotation stage.

### Example Workflow

The following workflow illustrates how tasks are prioritized:

<figure style="text-align: center">
  <img src="../../assets/examples/tasks_agents/twin_classification_transfer_source_workflow.png" width="100%"/>
  <figcaption>Project Workflow</figcaption>
</figure>

### STEP 1: Create the Agent file

Start by creating a new file named `agent.py` and include the following code:

<!--codeinclude-->

[agent.py](../../code_examples/tasks/prioritize_by_data_title.py)

<!--/codeinclude-->

- **Task Runner:** The code initializes a runner to process tasks.
- **Priority Assignment:** It defines a stage implementation that:
  - Extracts the data title of a task.
  - Parses the stem of the data title as an integer.
  - Assigns a priority as a number between `0` and `1`.
- **Task Routing:** Passes the task to the annotation stage by returning the correct pathway `UUID`.

---

### STEP 2: Running the Agent

Follow these steps to make the agent functional:

1. **Authentication & Setup:**
   - Export your private key as explained in the [authentication guide](../../authentication.md){target=\_blank}.
   - Install the `encord_agents` package, as detailed in the [installation guide](../../installation.md){target=\_blank}.
   
2. **Workflow Creation:**
   - Set up a workflow similar to the example shown above.

3. **Code Setup:**
   - Copy the code into an `agent.py` file.

4. **Adjust IDs:**
   - Update `<your_project_hash>`, `<your_agent_stage_uuid>`, and `<your_pathway_uuid>` in the code with the corresponding IDs from your workflow.

5. **Run the Agent:**
   - Execute the script by running the following command in your terminal:
     ```bash
     python agent.py
     ``` 

Your agent now assigns priorities to tasks based on their file names and routes them appropriately through the Workflow.

## Transferring Labels to a Twin Project

This example demonstrates how to transfer checklist labels from "Project A" and convert them into yes/no radio labels in "Project B."

### Assumptions

- **Ontology in Project A:**  
  The Ontology in Project A contains checklist classifications, as shown below:

  ![](../../assets/examples/tasks_agents/twin_classification_transfer_source_ontology.png){width=600}

- **Ontology in Project B:**  
  Every completed task in Project A is translated into a "model-friendly version" with radio classifications in Project B:

  ![](../../assets/examples/tasks_agents/twin_classification_transfer_sink_ontology.png){width=600}

> Notice that Project B has three classifications with identical names to those in Project A, but with two radio options each.

### STEP 1: Create the Agent file

An agent can perform this translation using the [`dep_twin_label_row` dependency](../../reference/task_agents.md#encord_agents.tasks.dependencies.dep_twin_label_row). For every label row from Project A, the agent automatically fetches the corresponding label row (and optionally the Workflow task) from Project B.

> **Note:** Both Project A and Project B must be linked to the same datasets.

Create an agent file named `twin_project.py` using the following code as a template.

<!--codeinclude-->

[twin_project.py](../../code_examples/tasks/twin_project.py)

<!--/codeinclude-->

### STEP 2: Set up Workflow

The following are examples of Workflows to be used. Create and save a Workflow template for each workflow.

- **Project A Workflow:**

  <figure style="text-align: center">
    <img src="../../assets/examples/tasks_agents/twin_classification_transfer_source_workflow.png" width="100%"/>
    <figcaption>Project A Workflow</figcaption>
  </figure>

- **Project B Workflow:**

  <figure style="text-align: center">
    <img src="../../assets/examples/tasks_agents/twin_classification_transfer_sink_workflow.png" width= "100%"/>
    <figcaption>Project B Workflow</figcaption>
  </figure>

With this configuration, all manual work happens in Project A, while Project B mirrors the transformed labels.

### STEP 3: Link Agent to Workflow

To link the agent to a workflow stage, use the following decorator:

```python
@runner.stage(stage="60d9f14f-755e-40fd-...")  # <- truncated for example
```

> The stage `uuid` in the decorator must match the "label transfer" agent stage `uuid` in Project A's Workflow.

### STEP 4: Prepare your Projects

1. **Set Up Projects:**
   - Create two Projects with the Ontologies and workflows illustrated above.
   - Ensure that the classification names match across both ontologies.
   - Both projects must point to the same dataset(s).

### STEP 5: Run the Agent

1. Export your private key, as explained in the [authentication guide](../../authentication.md){target=\_blank}.
2. Install the `encord_agents` package, as detailed in the [installation guide](../../installation.md){target=\_blank}.
3. Update the code to reflect:
  - `<project_hash_a>` and `<project_hash_b>` for your Projects.
  - The `stage` argument to match the agent stage `uuid` in Project A's workflow.
  - Completion pathway `uuids` for your Workflows.
4. Execute the agent file:

  ```bash
  python twin_project.py
  ```

Once the agent is running, tasks approved in Project A’s review stage move to the "Complete" stage in Project B, with the labels automatically translated and displayed.

## Pre-label video with _fake_ predictions

### Step 1: Define a _fake_ model for predictions

Suppose you have a _fake_ model like this one, which predicts labels, bounding boxes, and confidences.

<!--codeinclude-->

[Fake model predictions](../../code_examples/tasks/prelabel_videos.py) lines:29-52

<!--/codeinclude-->

### Step 2: Set up your Ontology

Create an Ontology that matches the expected output of your pre-labeling agent. For example:

<figure style="text-align: center">
  <img src="../../assets/examples/tasks_agents/prelabel_video_ontology.png" width="100%"/>
  Project ontology.
</figure>

### Step 3: Create a Workflow with a pre-labeling agent node

Create a Workflow template that includes a pre-labeling agent node before the annotation stage to automatically pre-label tasks with model predictions.

<figure style="text-align: center">
  <img src="../../assets/examples/tasks_agents/prelabel_video_workflow.png" width="100%"/>
  Project workflow.
</figure>

### Step 4: Create your pre-labeling agent

Create a pre-labeling agent using the following code as a template:

<!--codeinclude-->

[prelabel_video.py](../../code_examples/tasks/prelabel_videos.py) lines:10-77

<!--/codeinclude-->

This code uses the [`dep_video_iterator` dependency](../../reference/task_agents.md#encord_agents.tasks.dependencies.dep_video_iterator) to automatically load an iterator of frames as RGB numpy arrays from the video.

### Step 5: Run the agent

Follow these steps to execute the agent:

1. Ensure that you have exported your private key, as described in the [authentication section](../../authentication.md){target=\_blank}, and installed the `encord_agents` package, as explained in the [installation guide](../../installation.md){target=\_blank}.
2. Confirm that your Project includes a stage named **"pre-label"** with a pathway named **"annotate"**, and that its ontology resembles the example above.
3. Replace `<project_hash>` in the script with your own Project hash.
4. Execute the script using the following command:  

   ```bash
   python prelabel_video.py
   ```

### Step 6: Verify pre-labeled annotations

Once the agent completes, start annotating. You should see frames pre-populated with bounding boxes generated by the _fake_ model predictions.

## Further examples available soon

T following Agent examples will become available soon:

- Pre-labeling with YoloWorld
- Transcribing with Whisper
- Routing with Gemini
- Prioritizing with GPT-4o mini
- Evaluating Training projects
- HF Image segmentation API
- HF LLM API to classify frames
