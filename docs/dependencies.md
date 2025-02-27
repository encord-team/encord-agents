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

Adding custom dependencies is simple. Define a function that loads them, and then use that function as a dependency. The function itself can also rely on other dependencies if needed.

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
