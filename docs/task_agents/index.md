<div>
  <div style="display: flex; justify-content: space-between;">
    <div style="flex: 1; padding: 10px; text-align: center">
      <a href="https://docs.encord.com" target="_blank" style="text-decoration:none">
        <img alt="Documentation" src="/assets/tag-encord-docs.svg">
      </a>
      <a href="https://colab.research.google.com/drive/1nOVYEG-johzJK6R_mnkgjOiRJUuNIvOY?usp=sharing" target="_blank" style="text-decoration:none">
        <img alt="Task agent" src="/assets/tag-colab-task-agent.svg">
      </a>
      <a href="https://join.slack.com/t/encordactive/shared_invite/zt-1hc2vqur9-Fzj1EEAHoqu91sZ0CX0A7Q" target="_blank" style="text-decoration:none">
        <img alt="Join us on Slack" src="https://img.shields.io/badge/Join_Our_Community-4A154B?label=&logo=slack&logoColor=white">
      </a>
      <a href="https://twitter.com/encord_team" target="_blank" style="text-decoration:none">
        <img alt="Twitter Follow" src="https://img.shields.io/twitter/follow/encord_team?label=%40encord_team&amp;style=social">
      </a>
    </div>
  </div>
  <img width="100%" src="/assets/task-agent-banner.png" />
</div>

Task Agents are Workflow components in which a custom operation on all tasks in the Agent stage can be triggered. This allows you to set up pre-labeling, like using foundation models such as GPT-4o, automated quality assurance, or any other custom action you need for your workflow.

Here are some common use-cases:

- _Pre-labeling_ of your data, e.g., with your own model or off-the-shelf models.
- _Custom routing_ of data in the Project Workflow based on, e.g., metadata, annotation time, or label counts.
- _Dynamic prioritization_ of your tasks. This let's you "rearrange" tasks before sending them to review for example.
- _Custom "label assertions"_ that validate, e.g., number of labels or other constraints, before sending them for review.
- _Custom consensus computations_ by reading in labels from other Projects.

Task Agents must be triggered when a task reaches the associated agent state in the Project Workflow.

!!! tip
      Learning to build Task Agents is best done using [examples](../notebooks/task_agent_set_priority.ipynb).
