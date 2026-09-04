import unittest

from app.models.audit import AuditLogMutationError, prevent_audit_log_delete, prevent_audit_log_update


class AuditAppendOnlyTests(unittest.TestCase):
    def test_orm_update_is_rejected(self) -> None:
        with self.assertRaisesRegex(AuditLogMutationError, "cannot be updated"):
            prevent_audit_log_update()

    def test_orm_delete_is_rejected(self) -> None:
        with self.assertRaisesRegex(AuditLogMutationError, "cannot be deleted"):
            prevent_audit_log_delete()


if __name__ == "__main__":
    unittest.main()
