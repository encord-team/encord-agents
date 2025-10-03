from itertools import islice

from queue_runner_example import celery_function, runner


def batched(iterable, size):
    it = iter(iterable)
    batch = list(islice(it, size))
    while batch:
        yield batch
        batch = list(islice(it, size))


# Chunk tasks to batch process on individual workers
CHUNK_SIZE = 10


def main():
    """
    Populate the Celery queue with tasks from the Encord project.
    """
    # Iterate through all agent stages that have implementations
    for stage in runner.get_agent_stages():
        print(f"Processing stage: {stage.title} ({stage.uuid})")
        # Get all tasks for this stage
        for task in batched(stage.get_tasks(), CHUNK_SIZE):
            # Convert task to JSON spec and send to Celery queue
            task_specs = [task.model_dump_json() for task in task]

            # Send task to Celery worker
            celery_function.chunks(task_specs, CHUNK_SIZE).apply_async()
            print(f"Queued {len(task_specs)} tasks")

        break


if __name__ == "__main__":
    main()
