import pytest
from fastapi import HTTPException

from app.auth.tickets import issue_ticket, verify_ticket


def test_ticket_verify_and_consume() -> None:
    ticket = issue_ticket(sandbox_id="sb_1", subject="u1", ticket_type="vnc", scope="connect", ttl_sec=30)
    payload = verify_ticket(ticket, sandbox_id="sb_1", ticket_type="vnc", scope="connect", consume=True)
    assert payload["sandbox_id"] == "sb_1"
    with pytest.raises(HTTPException):
        verify_ticket(ticket, sandbox_id="sb_1", ticket_type="vnc", scope="connect", consume=True)

