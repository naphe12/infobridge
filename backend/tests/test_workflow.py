import unittest
from types import SimpleNamespace

from fastapi import HTTPException

from app.models.common import CaseStatus
from app.services.workflow import transition_case


class CaseTransitionTests(unittest.TestCase):
    def test_expected_transition_is_applied(self) -> None:
        exchange_case = SimpleNamespace(status=CaseStatus.DRAFT)

        transition_case(exchange_case, CaseStatus.SENT)

        self.assertEqual(exchange_case.status, CaseStatus.SENT)

    def test_skipping_a_transition_is_rejected(self) -> None:
        exchange_case = SimpleNamespace(status=CaseStatus.DRAFT)

        with self.assertRaises(HTTPException) as context:
            transition_case(exchange_case, CaseStatus.APPROVED)

        self.assertEqual(context.exception.status_code, 409)
        self.assertEqual(exchange_case.status, CaseStatus.DRAFT)

    def test_archived_case_is_terminal(self) -> None:
        exchange_case = SimpleNamespace(status=CaseStatus.ARCHIVED)

        with self.assertRaises(HTTPException):
            transition_case(exchange_case, CaseStatus.CLOSED)

    def test_assigned_case_must_be_started_before_response(self) -> None:
        exchange_case = SimpleNamespace(status=CaseStatus.ASSIGNED)

        with self.assertRaises(HTTPException):
            transition_case(exchange_case, CaseStatus.PENDING_VALIDATION)

        transition_case(exchange_case, CaseStatus.IN_PROGRESS)
        transition_case(exchange_case, CaseStatus.PENDING_VALIDATION)


if __name__ == "__main__":
    unittest.main()
