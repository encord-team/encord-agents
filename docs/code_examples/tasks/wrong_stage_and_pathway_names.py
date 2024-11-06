from encord.objects.ontology_labels_impl import LabelRowV2
from encord_agents.tasks import Runner

r = Runner()


@r.stage(stage="wrong")
def my_stage(lr: LabelRowV2) -> None:
    print(lr.data_title)


if __name__ == "__main__":
    # r()
    r.run()
