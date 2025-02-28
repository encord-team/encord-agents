# Celery Queue Runner Example

This example demonstrates how to use the Encord Agents QueueRunner with Celery and RabbitMQ for distributed task processing. This pattern can be used for any task that needs to be processed at scale, such as:

- Running machine learning inference on large datasets
- Batch processing of annotations
- Automated quality assurance checks
- Custom data preprocessing pipelines

## Authentication

Before running the example, you need to set up authentication:

1. Ensure you have an Encord account (register at [app.encord.com/register](https://app.encord.com/register))
2. Create an SSH key pair following [the documentation](https://docs.encord.com/platform-documentation/Annotate/annotate-api-keys)
3. Set one of these environment variables:
   ```bash
   # Either set the key content directly:
   export ENCORD_SSH_KEY="-----BEGIN OPENSSH PRIVATE KEY-----
   ...
   -----END OPENSSH PRIVATE KEY-----"
   
   # Or point to the key file:
   export ENCORD_SSH_KEY_FILE="/path/to/your/private_key"
   ```

> 💡 Consider creating a [service account](https://docs.encord.com/platform-documentation/GettingStarted/getting-started-service-accounts) for running agents

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Start RabbitMQ (using Docker):

```bash
docker run -d --hostname my-rabbit --name my-rabbit -p 5672:5672 -p 15672:15672 rabbitmq:management
```

3. Update the Project hash in `queue_runner_example.py` with your Encord Project hash.

## Running the Example

1. Start one or more Celery workers:
```bash
python worker.py
```

2. In a separate terminal, populate the queue with tasks:
```bash
python populate_queue.py
```

The workers automatically start processing tasks as they are added to the queue.

## Monitoring

You can monitor the RabbitMQ queue through the management interface at http://localhost:15672
(default credentials: guest/guest). This interface allows you to:

- Track queue lengths and processing rates
- Monitor worker status
- View error messages
- Access performance metrics

## Architecture

This example implements a distributed task processing pipeline with the following components:

1. **QueueRunner**: Wraps your agent implementation to handle Encord-specific logic
2. **Celery**: Manages the distributed task queue and workers
3. **RabbitMQ**: Acts as the message broker between components

The workflow follows these steps:

1. `populate_queue.py` gets tasks from Encord and sends them to the Celery queue
2. Celery workers pick up tasks and execute them using your agent implementation
3. Results are automatically handled by the QueueRunner wrapper, updating the Encord project

## Scaling

To scale processing horizontally, start more worker processes on the same or different machines:

```bash
python worker.py
```

This architecture has the following benefits:

- **Automatic load balancing**: Celery distributes tasks among available workers
- **Fault tolerance**: Failed tasks can be automatically retried
- **Scalability**: Add or remove workers without changing application code
- **Monitoring**: Built-in tools for tracking task progress and worker status

## Quick Start

1. Install the requirements
2. Start RabbitMQ
3. Update the project hash
4. Start one or more workers
5. Run the populate queue script

The workers process tasks as they become available in the queue.

## Customization

To adapt this example for your use case:

1. Modify the agent implementation in `queue_runner_example.py` with your task logic
2. Adjust worker settings in `worker.py` for your performance needs
3. Configure RabbitMQ settings if needed for your environment
4. Add any additional error handling or monitoring specific to your use case
