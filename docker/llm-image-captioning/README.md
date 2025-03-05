# LLM Image Captioning Container

## Dataset:
This agent works on datasets comprised exclusively of images.

## Workflow: 
An example includes: https://app.encord.com/workflow-templates/view/a7b7d551-7b29-429b-8e7d-08d5d2295109

This agent will work on any workflow that has an agent stage and will caption the images at that stage and move them onto the next stage.

The agent is configured to require exclusively images in the project and will throw a pre-execution error if this is not the case.

### Pathways

The agent will use simply the first pathway on the first agent.

## Ontology

The agent works with an Ontology that contains a top level text classification object. It will throw a pre-execution error if this is not the case. If there are multiple top level text classification objects, it'll choose the first such one.

## Execution
Please set the environment variables: `ENCORD_SSH_KEY` and `OPENAI_API_KEY`. Then the following command will propragate them down into the container. They will be used to authenticate with the Encord and OpenAI platform respectively

`docker run -e ENCORD_SSH_KEY -e OPENAI_API_KEY encord/encord-agent-llm-image-captioning:latest --project-hash=your-project-hash`

## Outcome

The agent will call OpenAI with the image and a small prompt, receive a caption, record this in the Label row and move the task to the next stage.
