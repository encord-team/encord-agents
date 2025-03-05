This agent works on datasets comprised exclusively of images.

This agent will work on any workflow that has an agent stage and will caption the images at that stage and move them onto the next stage

 docker run -e ENCORD_SSH_KEY -e OPENAI_API_KEY encord-agents-llm-image-captioning --project-hash=your-project-hash