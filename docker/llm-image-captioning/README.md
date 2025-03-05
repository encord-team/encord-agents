## Dataset:
This agent works on datasets comprised exclusively of images.

## Workflow: 
An example includes: https://app.encord.com/workflow-templates/view/a7b7d551-7b29-429b-8e7d-08d5d2295109

This agent will work on any workflow that has an agent stage and will caption the images at that stage and move them onto the next stage.

The agent is configured to require exclusively images in the project and will throw a pre-execution error if this is not the case.

## Ontology

The agent works with an Ontology that contains a top level text classification object. It will throw a pre-execution error if this is not the case

## Execution

docker run -e ENCORD_SSH_KEY -e OPENAI_API_KEY encord-agents-llm-image-captioning --project-hash=your-project-hash

## Outcome

The agent will call OpenAI with the image and a small prompt, receive a caption, record this in the Label row and move the task to the next stage.