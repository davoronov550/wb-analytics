"""Saved-search use-case tests — owner isolation, fake repo, no DB."""

from accounts.application.dto import SavedSearch
from accounts.application.use_cases.manage_saved_searches import ManageSavedSearches


class FakeSavedSearchRepo:
    def __init__(self):
        self._items: dict[int, SavedSearch] = {}
        self._counter = 0

    def create(self, *, owner_id, name, query, filters):
        self._counter += 1
        item = SavedSearch(
            id=self._counter, owner_id=owner_id, name=name, query=query, filters=filters
        )
        self._items[item.id] = item
        return item

    def list(self, owner_id):
        return [s for s in self._items.values() if s.owner_id == owner_id]

    def get(self, owner_id, saved_id):
        item = self._items.get(saved_id)
        return item if item and item.owner_id == owner_id else None

    def delete(self, owner_id, saved_id):
        if self.get(owner_id, saved_id) is None:
            return False
        del self._items[saved_id]
        return True


def test_saved_searches_are_owner_scoped():
    mgr = ManageSavedSearches(repository=FakeSavedSearchRepo())
    a = mgr.create(owner_id=1, name="A", query="наушники", filters={"minRating": 4})
    b = mgr.create(owner_id=2, name="B", query="чайники", filters={})
    assert [s.id for s in mgr.list(owner_id=1)] == [a.id]
    assert [s.id for s in mgr.list(owner_id=2)] == [b.id]


def test_delete_only_own():
    mgr = ManageSavedSearches(repository=FakeSavedSearchRepo())
    a = mgr.create(owner_id=1, name="A", query="q", filters={})
    assert mgr.delete(owner_id=2, saved_id=a.id) is False  # not the owner
    assert mgr.delete(owner_id=1, saved_id=a.id) is True
