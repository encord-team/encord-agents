from encord.objects.ontology_labels_impl import LabelRowV2

from encord_agents.tasks import Runner

runner = Runner(project_hash="<your_project_hash>")


@runner.stage("<your_agent_stage_uuid>")
def by_file_name(lr: LabelRowV2) -> str | None:
    # Assuming the data_title is of the format "%d.jpg"
    # and in the range [0; 100]
    priority = int(lr.data_title.split(".")[0]) / 100
    lr.set_priority(priority=priority)
    return "<your_pathway_uuid>"


if __name__ == "__main__":
    runner.run()
