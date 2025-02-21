<h1 align="center">
  <a href="https://encord.com"><img src="assets/landing-banner.png" alt="Encord logo"/></a>
</h1>

<div style="display: flex; justify-content: space-between;">
  <div style="flex: 1; padding: 10px; text-align: center">
    <a href="https://docs.encord.com" target="_blank" style="text-decoration:none">
      <img alt="Documentation" src="/assets/tag-encord-docs.svg">
    </a>
    <a href="https://colab.research.google.com/drive/1nOVYEG-johzJK6R_mnkgjOiRJUuNIvOY?usp=sharing" target="_blank" style="text-decoration:none">
      <img alt="Task agent" src="/assets/tag-colab-task-agent.svg">
    </a>
    <a href="https://colab.research.google.com/drive/1wvKAQ61JPebGnAT4nLXsfJRbx7dvtFdX?usp=sharing" target="_blank" style="text-decoration:none">
      <img alt="Editor agent" src="/assets/tag-colab-editor-agent.svg">
    </a>
    <a href="https://join.slack.com/t/encordactive/shared_invite/zt-1hc2vqur9-Fzj1EEAHoqu91sZ0CX0A7Q" target="_blank" style="text-decoration:none">
      <img alt="Join us on Slack" src="https://img.shields.io/badge/Join_Our_Community-4A154B?label=&logo=slack&logoColor=white">
    </a>
    <a href="https://twitter.com/encord_team" target="_blank" style="text-decoration:none">
      <img alt="Twitter Follow" src="https://img.shields.io/twitter/follow/encord_team?label=%40encord_team&amp;style=social">
    </a>
  </div>
</div>

Easily build agents for the Encord ecosystem.
With just few lines of code, you can take automation to the next level.

For a [workflow][docs-workflow]{ target="\_blank", rel="noopener noreferrer" } with a prioritization agent node looking like this:

![](assets/examples/tasks_agents/prioritize_by_title_workflow.png)

Here's how to build a [Task Agent](task_agents/index.md) that prioritizes annotation tasks based on data titles.

<!--codeinclude-->

[](code_examples/tasks/prioritize_by_data_title_specific.py)

<!--/codeinclude-->

> 💡 For the full end-to-end example, please see [here](getting_started.md).

This repository provides utility functions and examples for building both [editor agents][editor_agents]{ target="\_blank", rel="noopener noreferrer" } and [task agents][task_agents]{ target="\_blank", rel="noopener noreferrer" }.

**Key features:**

1. ⚡ **Easy**: Multiple template agents to be adapted and hosted via GCP, own infra, or cloud.
2. ⏩ **Convenient**: The library conveniently loads data via the [Encord SDK][encord_sdk]{ target="\_blank", rel="noopener noreferrer" } upon request.
3. 👨‍💻 **Focused**: With essential resources readily available, you can focus on what matters. Create agents with pre-existing (or custom) dependencies for loading labels and data.
4. 🤏 **Slim**: the library is slim at it's `core` and should not conflict with the dependencies of most projects.

**Choose what type of agent to use:**

![Decision tree for which agent to use](assets/decide-on-agent-type.png)

Upon [installation](./installation.md) and [authentication](./authentication.md), you should continue your reading as follows:

- If you plan to build an editor agent, please go to the [Editor agents section](editor_agents/index.md).
- If you plan to build a task agent, please go to the [Task agents section](task_agents/index.md).

[editor_agents]: https://docs.encord.com/platform-documentation/Annotate/automated-labeling/annotate-editor-agents
[task_agents]: https://docs.encord.com/platform-documentation/Annotate/automated-labeling/annotate-task-agents
[encord_sdk]: https://pypi.org/project/encord/
[docs-workflow]: https://docs.encord.com/sdk-documentation/projects-sdk/sdk-workflow-projects#workflow-projects
