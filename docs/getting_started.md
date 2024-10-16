> ℹ️ This example requires `python >= 3.10`. If you do not have python 3.10, we recommend using, e.g., [`pyenv`](https://github.com/pyenv/pyenv) to manage your python versions.

Here's the steps to follow to run your first [task agent](../task_agents/).
The example agent will modify the priority of each task before passing it along.
We also provide multiple [task agent examples](../task_agents/examples/) and [editor agent examples](../editor_agents/examples/).

### 1. Setup

Create a fresh directory and change to that directory.

```shell
mkdir my_project
cd my_project
```

Create a new virtual environment.

```shell
python -m venv venv
source venv/bin/activate
```

Now, install `encord-agents`.

```shell
python -m pip install "git+https://github.com/encord-team/encord-agents#egg=encord-agents[core]"
```

`# TODO ensure it works`

### 2. Encord workflow project

If you don't already have a [workflow project][docs-workflow-project] which includes an [agent stage][docs-workflow-agent], please [create one][docs-create-project].

In this example, we use a project workflow that looks like this:

![Project Workflow](/assets/project-workflow.png)

Notice the purple node in the workflow; It's an agent node **with name: `prioritize`**.
Furthermore, is has just one pathway called "annotate".

Copy the `Project ID` in the top left of the project page.

### 3. Define your agent

In your freshly created directory, create a python file.
In this example, we'll call it `agent.py`.

Copy paste the following template.

```python title="agent.py"
from encord.objects import LabelRowV2
from encord_agents.tasks import Runner

runner = Runner(project_hash="<your_project_hash>")

@runner.stage(name="pre-label")
def my_agent_logic(lr: LabelRowV2) -> str | None:
    location = "New York" if "NY" in lr.data_title else "San Francisco"

    priority = 0.
    if location == "New York":
        priority = 1.
    else if location == "San Francisco":
        priority = 0.5

    label_row.set_priority(priority=priority)

if __name__ == "__main__":
    from typer import Typer
    app = Typer(add_completion=False, rich_markup_mode="rich")
    app.command()(runner.__call__)
    app()
```

Notice the `my_agent_logic`, it recieves a [`LabelRowV2`][lrv2-class] instance.
That label row is associated with a task which is currently sitting in the `"prioritize"` agent stage.

Now, it's our job to define what's supposed to happen with it.
In this example, we'll keep it simple and assign a priority based on the file name.
If the file name contains `"london"` we'll give it high priority otherwise a low priority.

Update the `my_agent_logic` to look like this:

```python
@runner.stage(name="prioritize")
def my_agent_logic(lr: LabelRowV2) -> str | None:
    lr.set_priority(priority=float("london" in lr.data_title))
```

> **Too simple?**  
> If the example is too simple, please see the [task examples](../task_agents/examples)
> to find something more useful to your use-case.

### 4. Running the agent

From `agent.py` above, notice the last part.

```python
if __name__ == "__main__":
    from typer import Typer
    app = Typer(add_completion=False, rich_markup_mode="rich")
    app.command()(runner.__call__)
    app()
```

Run the agent by executing the following command:

```shell
python agent.py
```

[docs-workflow-project]: https://docs.encord.com/sdk-documentation/projects-sdk/sdk-workflow-projects#workflow-projects
[docs-workflow-agent]: https://docs.encord.com/platform-documentation/Annotate/annotate-projects/annotate-workflows-and-templates#agent
[docs-create-project]: https://docs.encord.com/platform-documentation/Annotate/annotate-projects/annotate-create-projects
[lrv2-class]: https://docs.encord.com/sdk-documentation/sdk-references/LabelRowV2
