# LLM Document Classification Container

## Dataset:
This agent works on datasets comprised exclusively of text files and will throw a pre-execution error if this is not the case.

## Workflow: 
This agent will work on any workflow that has an agent stage and will classify the images at that stage and move them onto the next stage.
An example includes: https://app.encord.com/workflow-templates/view/a7b7d551-7b29-429b-8e7d-08d5d2295109

## Ontology

The agent works with an Ontology that contains a top level radio classification object. It will throw a pre-execution error if this is not the case. If there are multiple such radios, it'll throw an error.
An alternative would be captioning as shown in the [captioning example](../llm-image-captioning/README.md)

## Execution

`docker run -e ENCORD_SSH_KEY -e OPENAI_API_KEY encord/encord-agent-llm-document-classification:latest --project-hash=your-project-hash`

## Outcome

The agent will classify the documents into the options in the selected Radio, record this in the Label row and move the task to the next stage. So it first embeds the radio options and then subsequently embeds the images and compares the similarity with the captions.
