# Dependencies

When you are defining your agents, we've made it easy to inject essential dependencies like the a path to the underlying asset, frame iterators, etc.
Similarly, you can also inject your own custom dependencies, if you need to.

The way you inject dependencies is by type-annotating your agent function variables with the `Depends` class.

```python
from typing_extensions import Annotated

from encord.core.dependencies import Depends
# or from fastapi import Depends # if you are building a fastapi app

from encord.{module}.dependencies import dep_single_frame

def my_agent(frame: Annotated[np.ndarray, Depends(dep_single_frame)]):
    # the frame will be available here.
```

The `{module}` depends on which type of agent you're building.
Please see the [references section](reference/editor_agents.md#encord_agents.gcp.dependencies) for more details on available agents.

## Custom dependencies

Custom dependencies are also easy. Just define how to load them in a function and depend on that function.
The function it self can also depend on other dependencies.

Here is an example:

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
