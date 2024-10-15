# Installation

The project comes with multiple different sets of dependencies to accomodate easy development for different use cases.
Please see below for the right option for your use-case.

> ℹ️ This example requires `python >= 3.10`. If you do not have python 3.10, we recommend using, e.g., [`pyenv`](https://github.com/pyenv/pyenv) to manage your python versions.

**FastAPI Editor Agents**  
If you are building a new FastAPI application for editor agents, you should install the project with

```
python -m pip install "encord-agents[fastapi]"
```

**GCP Editor Agents**  
If you plan to use the project with GCPs `functions_framework`, then do

```
python -m pip install "encord-agents[gcp-functions]"
```

**Task Agents or your own infra**

Finally, if you want to [build task agents](../task_agents/) or manage all the dependencies on your own, the only necessary dependencies for the `core` module
can be installed with

```
python -m pip install "encord-agents[core]"
```

> 💡 For any of the the install options above, you will can find exactly what each of these options require from the project [pyproject.toml](https://github.com/encord-team/encord-agents/blob/main/pyproject.toml){ target=blank } file.
