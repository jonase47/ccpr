"""test_contract_seam.py – Ensures the contract mixin forces backend authors to
supply their own item-creation path, instead of silently inheriting a filesystem
write that a non-filesystem backend (e.g. a future youtrack backend) never reads.
"""

import unittest

from .contract import WorkItemsContractTestCase


class _BareContractSubclass(WorkItemsContractTestCase):
    """A stand-in for a backend author who forgot to implement create_item()."""

    def create_backend(self, workitems_dir):
        return object()  # never exercised — only create_item() is under test here


class ContractSeamTest(unittest.TestCase):
    def test_create_item_is_not_implemented_by_default(self):
        subject = _BareContractSubclass()

        with self.assertRaises(NotImplementedError):
            subject.create_item("WI-0001")


if __name__ == "__main__":
    unittest.main()
