Before getting started, ensure that you have:

* `python >= 3.10`. If you do not have Python 3.10, we recommend using [`pyenv`](https://github.com/pyenv/pyenv){ target="\_blank", rel="noopener noreferrer" } to manage your Python versions.
* The ability to authenticate with Encord.
* [Installed the Encord Agents library](./installation.md).

The following example shows how to create a simple [Task Agent](task_agents/index.md).
to change the priority of each task before moving it to the next stage of the Workflow.

!!! tip
    We also provide more detailed [Task Agent examples](notebooks/task_agent_set_priority.ipynb) and [editor agent examples](editor_agents/examples/index.md).


## 1. Create Encord Project

Create a [Project in Encord](https://docs.encord.com/platform-documentation/Annotate/annotate-projects/annotate-create-projects) containing the following Workflow with an [agent stage](https://docs.encord.com/platform-documentation/Annotate/annotate-projects/annotate-workflows-and-templates#agent).

![Project Workflow](assets/project-workflow.png)

The purple node in the Workflow is an agent node named `pre-label`. It has a single pathway called `annotate` that moves tasks to the next stage in the Workflow.

Copy the `Project ID` in the top left of the Project page.

!!! tip
    After [authenticating](./authentication.md), you can check if your existing Project has any agent nodes by running this command:
    ```shell
    encord-agents print agent-nodes <your_project_hash>
    ```
    If the project has agent nodes in the Workflow, you should see a list similar to this:
    ```shell
    AgentStage(title="pre-label", uuid="b9c1363c-615f-4125-ae1c-a81e19331c96")
    AgentStage(title="evaluate", uuid="28d1bcc9-6a3a-4229-8c06-b498fcaf94a0")
    ```

## 2. Define the Agent

In the directory you created for your agents, create a Python file. In this example we use `agent.py`.

Copy paste the following template in to the Python file:

```python title="agent.py"
from encord.objects import LabelRowV2
from encord_agents.tasks import Runner

runner = Runner(project_hash="<your_project_hash>")

@runner.stage(stage="pre-label")
def my_agent_logic(lr: LabelRowV2) -> str:
    # ...
    return "annotate"

if __name__ == "__main__":
    runner.run()
```

The `my_agent_logic` function takes a [`LabelRowV2`][lrv2-class]{ target="\_blank", rel="noopener noreferrer" } instance belonging to a task currently in the `"pre-label"` agent stage. The agent then returns the name of the pathway the task should follow once completed.  

We must define how this data is handled. In this example, we keep it simple by assigning priority based on the file name. If the file name contains `"london"`, it gets assigned a high priority; otherwise, it gets assigned low priority.  

```python
@runner.stage(stage="pre-label")
def my_agent_logic(lr: LabelRowV2) -> str:
    lr.set_priority(priority=float("london" in lr.data_title))
    return "annotate"
```

> **Too simple?**  
> If the example is too simple, see the [task examples](task_agents/index.md)
> to find something more relevant to your use case.

## 3. Run the Agent

The Agent must be run in order for tasks to be moved on to the next Workflow stage.

Run the agent by executing the following command:

```shell
python agent.py
```

[docs-workflow-project]: https://docs.encord.com/sdk-documentation/projects-sdk/sdk-workflow-projects#workflow-projects
[docs-workflow-agent]: https://docs.encord.com/platform-documentation/Annotate/annotate-projects/annotate-workflows-and-templates#agent
[docs-create-project]: https://docs.encord.com/platform-documentation/Annotate/annotate-projects/annotate-create-projects
[lrv2-class]: https://docs.encord.com/sdk-documentation/sdk-references/LabelRowV2
