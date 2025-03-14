# Gemma 3 Routing Container

## Dataset:
This agent works on datasets comprised of images, text files and videos and will throw a pre-execution error if this is not the case.

## Workflow: 
This agent will work on any workflow that has an agent stage and will route the images at that stage and move them onto the next stage.

## Ontology

The agent is Ontology agnostic

## Execution

`docker run --gpus all -e ENCORD_SSH_KEY -e HUGGINGFACE_API_KEY encord/encord-agent-gemma-3-routing-container:latest --project-hash=your-project-hash`
Note you may need to follow: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html

## Outcome
The model will route the tasks sitting at the first stage to the various pathways. It will download the checkpoint and perform inference.