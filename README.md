<p align="center">
<a href="https://agents-docs.encord.com/" target="_blank">Documentation</a> |
<a href="https://colab.research.google.com/drive/1wvKAQ61JPebGnAT4nLXsfJRbx7dvtFdX?usp=sharing" target="_blank">Try it Now</a> |
<a href="https://encord.com/blog/" target="_blank">Blog</a> |
<a href="https://join.slack.com/t/encordactive/shared_invite/zt-1hc2vqur9-Fzj1EEAHoqu91sZ0CX0A7Q" target="_blank">Join our Community</a>
</p>

<h1 align="center">
    <a href="https://encord.com"><img src="https://raw.githubusercontent.com/encord-team/encord-agents/main/docs/assets/landing-banner.png" alt="Encord logo"/></a>
</h1>

<div style="display: flex; justify-content: space-between;">
  <div style="flex: 1; padding: 10px;">
    <a href="https://agents-docs.encord.com/" target="_blank" style="text-decoration:none">
      <img alt="Documentation" src="https://img.shields.io/badge/docs-Online-blue">
    </a>
    <a href="https://github.com/encord-team/encord-notebooks" target="_blank" style="text-decoration:none">
      <img alt="Encord Notebooks" src="https://img.shields.io/badge/Encord_Notebooks-blue?logo=github&label=&labelColor=181717">
    </a>
    <a href="https://colab.research.google.com/drive/1wvKAQ61JPebGnAT4nLXsfJRbx7dvtFdX?usp=sharing" target="_blank" style="text-decoration:none">
            <img alt="Try editor agent" src="https://raw.githubusercontent.com/encord-team/encord-agents/main/docs/assets/tag-colab-editor-agent.svg">
    </a>
    <a href="https://colab.research.google.com/drive/1wvKAQ61JPebGnAT4nLXsfJRbx7dvtFdX?usp=sharing" target="_blank" style="text-decoration:none">
            <img alt="Try task agent" src="https://raw.githubusercontent.com/encord-team/encord-agents/main/docs/assets/tag-colab-task-agent.svg">
    </a>
    <a href="https://join.slack.com/t/encordactive/shared_invite/zt-1hc2vqur9-Fzj1EEAHoqu91sZ0CX0A7Q" target="_blank" style="text-decoration:none">
      <img alt="Join us on Slack" src="https://img.shields.io/badge/Join_Our_Community-4A154B?label=&logo=slack&logoColor=white">
    </a>
    <a href="https://twitter.com/encord_team" target="_blank" style="text-decoration:none">
      <img alt="Twitter Follow" src="https://img.shields.io/twitter/follow/encord_team?label=%40encord_team&amp;style=social">
    </a>
  </div>
  <div style="flex: 1; padding: 10px;">
    <img alt="Python versions" src="https://img.shields.io/pypi/pyversions/encord-agents">
    <a href="https://pypi.org/project/encord-agents/" target="_blank" style="text-decoration:none">
      <img alt="PyPi project" src="https://img.shields.io/pypi/v/encord-agents">
    </a>
    <img alt="PRs Welcome" src="https://img.shields.io/badge/PRs-Welcome-blue">
    <img alt="Licence" src="https://img.shields.io/github/license/encord-team/encord-agents">
  </div>
</div>

Easily build agents for the Encord echo system.
With just few lines of code, you can take automation to the next level.

```shell
python -m pip install encord-agents
```

**Key features:**

1. ⚡ **Easy**: Multiple template agents to be adapted and hosted via GCP, own infra, or cloud.
2. ⏩ **Convenient**: The library conveniently loads data via the [Encord SDK][encord_sdk] upon request.
3. 👨‍💻 **Focused**: With essential resources readily available, you can focus on what matters. Create agents with pre-existing (or custom) dependencies for loading labels and data.
4. 🤏 **Slim**: the library is slim at it's `core` and should not conflict with the dependencies of most projects.

> 💡 For the full documentation and end-to-end examples, please see [here][docs-url].

Here are some use-cases:

![Decision tree for which agent to use](https://raw.githubusercontent.com/encord-team/encord-agents/main/docs/assets/decide-on-agent-type.png)

Here's how to build an Agent:

```python
from uuid import UUID
from encord.objects.ontology_labels_impl import LabelRowV2
from encord_agents.tasks import Runner

runner = Runner(project_hash="<your_project_hash>")


@runner.stage("<your_agent_stage_uuid>")
def by_file_name(lr: LabelRowV2) -> UUID | None:
    # Assuming the data_title is of the format "%d.jpg"
    # and in the range [0; 100]
    priority = int(lr.data_title.split(".")[0]) / 100
    lr.set_priority(priority=priority)
    return "<your_pathway_uuid>"


if __name__ == "__main__":
    runner.run()
```

You can also inject dependencies:

```python
from typing_extensions import Annotated

from encord.objects import LabelRowV2
from encord_agents.tasks import Runner, Depends

runner = Runner(project_hash="<your_project_hash>")

def my_custom_dependency(label_row: LabelRowV2) -> dict:
    # e.g., look up additional data in own db
    return db.query("whatever")

@runner.stage(stage="<my_stage_name>")
def by_custom_data(
    custom_data: Annotated[dict, Depends(my_custom_dependency)]
) -> str:
    # `custom_data` automatically injected here.
    # ... do your thing
    # then, return name of task pathway.


if __name__ == "__main__":
    runner.run()
```

Please visit our [📖 Documentation][docs-url] for a complete reference to how to use the agents library.

[docs-url]: https://agents-docs.encord.com/
[encord_sdk]: https://pypi.org/project/encord/
[fastapi]: https://fastapi.tiangolo.com/
