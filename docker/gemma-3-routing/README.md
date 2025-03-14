# Gemma 3 Routing Container

## Dataset:
This agent works on datasets comprised of images, text files and videos and will throw a pre-execution error if this is not the case.

## Workflow: 
This agent will work on any workflow that has an agent stage and will route the images at that stage and move them onto the next stage.

## Ontology

The agent is Ontology agnostic

## Execution

`docker run -e ENCORD_SSH_KEY -e HUGGINGFACE_API_KEY encord/encord-agent-gemma-3-routing-container:latest --project-hash=your-project-hash`

## Outcome

TODO
