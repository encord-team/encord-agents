from queue_runner_example import celery_function, runner


def main():
    """
    Populate the Celery queue with tasks from the Encord project.
    """
    # Iterate through all agent stages that have implementations
    for stage in runner.get_agent_stages():
        print(f"Processing stage: {stage.title} ({stage.uuid})")

        # Get all tasks for this stage
        for task in stage.get_tasks():
            # Convert task to JSON spec and send to Celery queue
            task_spec = task.model_dump_json()

            # Send task to Celery worker
            celery_function.delay(task_spec)
            print(f"Queued task: {task.uuid}")

        break


if __name__ == "__main__":
    main()
