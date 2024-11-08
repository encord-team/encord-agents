from __future__ import annotations

from uuid import UUID

from encord.orm.dataset import DataRow
from encord.project import Project
from encord.storage import StorageItem

from encord_agents.core.utils import get_user_client


class DataLookup:
    __instances__: dict[UUID, DataLookup] = {}

    def __init__(self, dataset_hashes: list[str | UUID] | None = None) -> None:
        self.user_client = get_user_client()
        self.datasets = {UUID(d): self.user_client.get_dataset(d) for d in map(str, dataset_hashes or [])}
        self.data_rows = {dr.uid: dr for dataset in self.datasets.values() for dr in dataset.data_rows}

    @classmethod
    def sharable(cls, project: Project) -> DataLookup:
        ph = UUID(project.project_hash)
        if ph not in cls.__instances__:
            cls.__instances__[ph] = cls([ds.dataset_hash for ds in project.list_datasets()])
        return cls.__instances__[ph]

    def get_data_row(self, data_hash: str | UUID, dataset_hash: str | UUID | None = None) -> DataRow:
        dr = self.data_rows.get(str(data_hash))
        if dr is None:
            if dataset_hash is not None:
                dataset = self.user_client.get_dataset(str(dataset_hash))
                self.datasets[UUID(str(dataset_hash))] = dataset
                self.data_rows.update({dr.uid: dr for dr in dataset.data_rows})
            else:
                raise ValueError(
                    "Cannot identify a data row without knowing the dataset hash. Please provide it to the function call or to the constructor of the `DataLookup`"
                )
            dr = self.data_rows.get(str(data_hash))
        if dr is None:
            raise ValueError("DatasetCache was not able to locate data row from data hash")
        return dr

    @property
    def backing_item_uuids(self) -> list[UUID]:
        """
        Get all backing item uuids for all data rows in the data lookup.
        """
        return [dr.backing_item_uuid for dr in self.data_rows.values()]

    def get_storage_item(
        self, data_hash: str | UUID, dataset_hash: str | UUID | None = None, sign_url: bool = False
    ) -> StorageItem:
        """

        Args:
            data_hash: Data hash for the asset for which you need the underlying storage item.
            dataset_hash: If you didn't provide the associated dataset hash in the constructor,
                this is your last chance.
            sign_url: If `True`, pre-fetch a signed URLs for the items (otherwise the URLs will be signed on demand).

        Raises:
            ValueError: Mainly if underlying data row cannot be found.

        Returns:
            The underlying storage item from which, e.g., client metadata can be updated.

        """
        try:
            dr = self.get_data_row(data_hash, dataset_hash)
        except ValueError:
            raise ValueError(
                "DatasetCache was not able to locate storage_item because the associated data row could not be identified."
            )

        return self.user_client.get_storage_item(dr.backing_item_uuid)

    def get_storage_items(
        self, data_hashes: list[str | UUID], dataset_hash: str | UUID | None = None, sign_urls: bool = False
    ) -> list[StorageItem]:
        """

        Args:
            data_hashes: Data hashes for the assets for which you need the underlying storage items.
            dataset_hash: If you didn't provide the associated dataset hash in the constructor,
                this is your last chance.
            sign_urls: If `True`, pre-fetch a signed URLs for the items (otherwise the URLs will be signed on demand).
            return self.user_client.get_storage_items()

        Raises:
            ValueError: Mainly if underlying data row cannot be found.

        Returns:
            list of underlying storage items from which, e.g., client metadata can be updated.
        """
        try:
            data_rows = [self.get_data_row(i, dataset_hash) for i in data_hashes]
        except ValueError:
            raise ValueError("Failed to load storage items because one or more data rows could not be obtained")

        return self.user_client.get_storage_items([dr.backing_item_uuid for dr in data_rows])
