## Introduction

When writing agents, you often rely on common resources, whether data for running your agent or for recording the output. Instead of manually setting up these resources with extensive boilerplate code, we use **dependency injection** to declaratively acquire them, allowing you to focus on developing your agent.

## What is Dependency Injection

We follow dependencies as defined in: [Fastapi Dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/).

> "Dependency Injection" means, in programming, that there is a way for your code (in this case, your path operation functions) to declare things that it requires to work and use: "dependencies".
> 
> And then, that system(e.g. FastAPI or encord-agents) will take care of doing whatever is needed to provide your code with those needed dependencies ("inject" the dependencies)

Please read there further for more intuition and examples of the principle and the practice.

## Practice

When defining your agents, you can easily inject essential dependencies, such as the path to the underlying asset or frame iterators. You can also add custom dependencies if needed.  

To inject dependencies, simply type-annotate your agent function variables using the `Depends` class.

```python
from typing_extensions import Annotated

from encord.core.dependencies import Depends
# or from fastapi import Depends # if you are building a fastapi app

from encord.{module}.dependencies import dep_single_frame

def my_agent(frame: Annotated[np.ndarray, Depends(dep_single_frame)]):
    # the frame will be available here.
```

The `{module}` depends on which type of agent you're building.
Please see the [references section](reference/editor_agents.md#encord_agents.gcp.dependencies) for more details on available dependencies.

## Custom Dependencies


To add a custom dependencies:

1. Define a function to load the dependencies.
2. Use that function as a dependency.

```python
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

```

The function itself can also rely on other dependencies if needed, allowing more complicated resource acquisition. See the internals of `dep_video_iterator` for an example of this. 