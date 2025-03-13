# Detr Video Labeling Container

## Dataset:
This agent works on datasets comprised exclusively of videos and will throw a pre-execution error if this is not the case.

## Workflow: 
This agent will work on any workflow that has an agent stage and will annotate the videos at that stage with bounding boxes and move them onto the next stage.

## Ontology

The agent works with an Ontology that contains a bounding box. It will throw a pre-execution error if this is not the case. If there are multiple such radios, it'll throw an error. 

## Execution

`docker run -e ENCORD_SSH_KEY encord/encord-agent-detr-video-labeling:latest --project-hash=your-project-hash`

## Outcome

The agent will annotate the videos with bounding boxes, record this in the Label row and move the task to the next stage.
