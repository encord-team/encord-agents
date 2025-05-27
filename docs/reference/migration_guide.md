# Migration Guide

This guide helps you migrate from deprecated features to their recommended replacements.

## DataLookup Deprecation (v0.2.10)

!!! warning "Deprecated"
    The `DataLookup` class and `dep_data_lookup` dependency functions are deprecated and will be removed in version 0.2.10.

### Why is DataLookup being deprecated?

The `DataLookup` class was designed to provide easy access to data rows and storage items, but it has several limitations:

- **Complexity**: It maintains internal state and caching that can be confusing
- **Performance**: It loads entire datasets into memory unnecessarily
- **Redundancy**: The functionality is better provided by existing dependencies
- **Maintenance**: It duplicates functionality available in the Encord SDK

### Migration Paths

#### 1. Accessing Storage Items (Most Common Use Case)

**Before (Deprecated):**
```python
from typing_extensions import Annotated
from encord_agents.core.dependencies.shares import DataLookup
from encord_agents.tasks.dependencies import dep_data_lookup

@runner.stage("my_stage")
def my_agent(
    task: AgentTask,
    lookup: Annotated[DataLookup, Depends(dep_data_lookup)]
) -> str:
    storage_item = lookup.get_storage_item(task.data_hash)
    print(storage_item.client_metadata)
    return "next_stage"
```

**After (Recommended):**
```python
from typing_extensions import Annotated
from encord.storage import StorageItem
from encord_agents.tasks.dependencies import dep_storage_item

@runner.stage("my_stage")
def my_agent(
    task: AgentTask,
    storage_item: Annotated[StorageItem, Depends(dep_storage_item)]
) -> str:
    # storage_item is directly available
    print(storage_item.client_metadata)
    return "next_stage"
```

#### 2. Editor Agents Migration

**Before (Deprecated):**
```python
from typing_extensions import Annotated
from encord_agents import FrameData
from encord_agents.core.dependencies.shares import DataLookup
from encord_agents.gcp.dependencies import dep_data_lookup
# or from encord_agents.aws.dependencies import dep_data_lookup
# or from encord_agents.fastapi.dependencies import dep_data_lookup

@editor_agent()
def my_agent(
    frame_data: FrameData,
    lookup: Annotated[DataLookup, Depends(dep_data_lookup)]
):
    storage_item = lookup.get_storage_item(frame_data.data_hash)
    print(storage_item.client_metadata)
```

**After (Recommended):**
```python
from typing_extensions import Annotated
from encord.storage import StorageItem
from encord_agents import FrameData
from encord_agents.gcp.dependencies import dep_storage_item
# or from encord_agents.aws.dependencies import dep_storage_item
# or from encord_agents.fastapi.dependencies import dep_storage_item

@editor_agent()
def my_agent(
    frame_data: FrameData,
    storage_item: Annotated[StorageItem, Depends(dep_storage_item)]
):
    # storage_item is directly available
    print(storage_item.client_metadata)
```

### Benefits of Migration

1. **Simpler Code**: Direct dependency injection eliminates the need for lookup calls
2. **Better Performance**: No unnecessary dataset loading or caching
3. **Type Safety**: Better IDE support and type checking
4. **Future-Proof**: Uses the recommended patterns that will continue to be supported
5. **Cleaner Dependencies**: Explicit dependencies make code easier to understand and test

### Timeline

- **Current**: Deprecation warnings are shown when using `DataLookup` or `dep_data_lookup`
- **Version 0.2.10**: `DataLookup` and `dep_data_lookup` will be removed

### Need Help?

If you encounter issues during migration or have use cases not covered by this guide:

1. Check the [Dependencies documentation](../dependencies.md) for more examples
2. Review the [API reference](./core.md) for available dependencies
3. Open an issue on the [GitHub repository](https://github.com/encord-team/encord-agents) for additional support 