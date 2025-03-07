# Clip Image Classification Container

## Dataset:
This agent works on datasets comprised exclusively of videos and will throw a pre-execution error if this is not the case.

## Workflow: 
This agent will work on any workflow that has an agent stage and will classify the images at that stage and move them onto the next stage.

## Ontology

The agent works with an Ontology that contains a top level radio classification object. It will throw a pre-execution error if this is not the case. If there are multiple such radios, it'll throw an error. 

## Execution

`docker run -e ENCORD_SSH_KEY encord-agent-detr-video-prelabeling --project-hash=your-project-hash`

## Outcome

The agent will classify the images into the options in the selected Radio, record this in the Label row and move the task to the next stage. So it first embeds the radio options and then subsequently embeds the images and compares the similarity with the captions.
