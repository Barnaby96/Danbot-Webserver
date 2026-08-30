import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from main import create_app
from routes import dink
from utils import database


@pytest.fixture(autouse=True)
def dink_identity_test_database():
    if os.getenv("PGDATABASE") != "danbot_test":
        pytest.fail(
            "Dink identity tests must only run against "
            "PGDATABASE=danbot_test"
        )

    database.reset_tables()
    yield


@pytest.fixture()
def client():
    app = create_app()
    app.config["TESTING"] = True

    with app.test_client() as test_client:
        yield test_client


def create_test_user(
    username,
    email,
    password,
    is_admin=False
):
    database.add_user(
        username,
        email,
        password
    )

    if is_admin:
        with database.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                UPDATE users
                SET is_admin = TRUE
                WHERE email = %s
                ''',
                (email,)
            )


def login_test_user(
    client,
    email,
    password
):
    return client.post(
        "/login",
        data={
            "email": email,
            "password": password
        }
    )


def create_test_player(
    player_name,
    team_name="Identity Test Team"
):
    database.add_team(
        team_name,
        0,
        ""
    )

    team = database.get_team_by_name(
        team_name
    )

    database.add_player(
        player_name,
        0,
        0,
        0,
        team[3],
        0
    )


def ingest_observation(
    player_name,
    dink_account_hash,
    boss
):
    return dink.ingest_dink_event(
        {
            "playerName": player_name,
            "dinkAccountHash": dink_account_hash,
            "type": "KILL_COUNT",
            "extra": {
                "boss": boss,
                "killCount": 1
            }
        }
    )


def login_admin(client):
    create_test_user(
        "Identity Admin",
        "identity-admin@example.test",
        "test-password",
        is_admin=True
    )

    response = login_test_user(
        client,
        "identity-admin@example.test",
        "test-password"
    )

    assert response.status_code == 302


def test_admin_can_view_pending_dink_identity(client):
    create_test_player(
        "Pending Tester"
    )

    ingest_observation(
        "Pending Tester",
        "pending-test-hash",
        "Goblin"
    )

    login_admin(client)

    response = client.get(
        "/admin/dink_identities"
    )

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert "Dink Identity Review" in page
    assert "PENDING" in page
    assert "Pending Tester" in page
    assert "Identity Test Team" in page
    assert "pending-test-hash" in page
    assert "Awaiting verification" in page
    assert "1/3 observations" in page


def test_admin_can_view_linked_dink_identity(client):
    create_test_player(
        "Linked Tester"
    )

    for boss in (
        "Goblin",
        "Man",
        "Spider"
    ):
        ingest_observation(
            "Linked Tester",
            "linked-test-hash",
            boss
        )

    login_admin(client)

    response = client.get(
        "/admin/dink_identities"
    )

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert "LINKED" in page
    assert "Verified and linked" in page
    assert "Linked Tester" in page
    assert "Identity Test Team" in page
    assert "linked-test-hash" in page


def test_admin_sees_player_not_found_state(client):
    for boss in (
        "Goblin",
        "Man",
        "Spider"
    ):
        ingest_observation(
            "Missing Tester",
            "missing-player-test-hash",
            boss
        )

    login_admin(client)

    response = client.get(
        "/admin/dink_identities"
    )

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert "PLAYER NOT FOUND" in page
    assert "Missing Tester" in page
    assert "missing-player-test-hash" in page
    assert (
        "Three or more observations but no "
        "matching DanBot player"
    ) in page


def test_admin_sees_conflicting_rsn_reason(client):
    create_test_player(
        "Original Tester"
    )

    ingest_observation(
        "Original Tester",
        "rsn-conflict-test-hash",
        "Goblin"
    )

    ingest_observation(
        "Different Tester",
        "rsn-conflict-test-hash",
        "Man"
    )

    login_admin(client)

    response = client.get(
        "/admin/dink_identities"
    )

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert "CONFLICT" in page
    assert "Hash seen with conflicting RSNs" in page
    assert "Original Tester" in page
    assert "Different Tester" in page
    assert "rsn-conflict-test-hash" in page


def test_admin_sees_existing_linked_hash_reason(client):
    create_test_player(
        "Double Hash Tester"
    )

    for boss in (
        "Goblin",
        "Man",
        "Spider"
    ):
        ingest_observation(
            "Double Hash Tester",
            "primary-test-hash",
            boss
        )

    for boss in (
        "Rat",
        "Cow",
        "Chicken"
    ):
        ingest_observation(
            "Double Hash Tester",
            "secondary-test-hash",
            boss
        )

    login_admin(client)

    response = client.get(
        "/admin/dink_identities"
    )

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert "CONFLICT" in page
    assert (
        "Player already linked to another "
        "Dink account"
    ) in page
    assert "primary-test-hash" in page
    assert "secondary-test-hash" in page

def test_manual_link_leaves_pending_events_unprocessed(client):
    create_test_player(
        "Manual Link Tester"
    )

    ingest_result = ingest_observation(
        "Manual Link Tester",
        "manual-link-test-hash",
        "Goblin"
    )

    player = database.get_player_by_name(
        "Manual Link Tester"
    )

    link_result = database.manually_link_dink_identity(
        "manual-link-test-hash",
        player[0]
    )

    assert link_result["status"] == "LINKED"
    assert link_result["player_id"] == player[0]

    identity = database.get_dink_identity_by_hash(
        "manual-link-test-hash"
    )

    assert identity is not None
    assert identity[1] == player[0]
    assert identity[3] == "LINKED"

    event = database.get_dink_event_by_id(
        ingest_result["event_id"]
    )

    assert event is not None
    assert event[5] is None
    assert event[10] == "PENDING_IDENTITY"
    assert event[12] is None

def test_manual_link_refuses_second_hash_for_player(client):
    create_test_player(
        "Double Manual Tester"
    )

    for boss in (
        "Goblin",
        "Man",
        "Spider"
    ):
        ingest_observation(
            "Double Manual Tester",
            "primary-manual-test-hash",
            boss
        )

    ingest_observation(
        "Double Manual Tester",
        "secondary-manual-test-hash",
        "Rat"
    )

    player = database.get_player_by_name(
        "Double Manual Tester"
    )

    link_result = database.manually_link_dink_identity(
        "secondary-manual-test-hash",
        player[0]
    )

    assert link_result["status"] == "PLAYER_ALREADY_LINKED"
    assert link_result["player_id"] == player[0]
    assert (
        link_result["existing_linked_hash"]
        == "primary-manual-test-hash"
    )

    primary_identity = database.get_dink_identity_by_hash(
        "primary-manual-test-hash"
    )

    secondary_identity = database.get_dink_identity_by_hash(
        "secondary-manual-test-hash"
    )

    assert primary_identity is not None
    assert primary_identity[1] == player[0]
    assert primary_identity[3] == "LINKED"

    assert secondary_identity is not None
    assert secondary_identity[1] is None
    assert secondary_identity[3] == "PENDING"
    assert secondary_identity[6] is None

def test_admin_can_manually_link_dink_identity(client):
    create_test_player(
        "Route Link Tester"
    )

    ingest_result = ingest_observation(
        "Route Link Tester",
        "route-link-test-hash",
        "Goblin"
    )

    player = database.get_player_by_name(
        "Route Link Tester"
    )

    login_admin(client)

    response = client.post(
        "/admin/dink_identities",
        data={
            "action": "manual_link",
            "dink_account_hash": "route-link-test-hash",
            "player_id": str(player[0])
        }
    )

    assert response.status_code == 302
    assert (
        response.headers["Location"]
        .endswith("/admin/dink_identities")
    )

    identity = database.get_dink_identity_by_hash(
        "route-link-test-hash"
    )

    assert identity is not None
    assert identity[1] == player[0]
    assert identity[3] == "LINKED"

    event = database.get_dink_event_by_id(
        ingest_result["event_id"]
    )

    assert event is not None
    assert event[5] is None
    assert event[10] == "PENDING_IDENTITY"
    assert event[12] is None

def test_admin_manual_link_refuses_second_hash(client):
    create_test_player(
        "Route Double Tester"
    )

    for boss in (
        "Goblin",
        "Man",
        "Spider"
    ):
        ingest_observation(
            "Route Double Tester",
            "route-primary-test-hash",
            boss
        )

    ingest_observation(
        "Route Double Tester",
        "route-secondary-test-hash",
        "Rat"
    )

    player = database.get_player_by_name(
        "Route Double Tester"
    )

    login_admin(client)

    response = client.post(
        "/admin/dink_identities",
        data={
            "action": "manual_link",
            "dink_account_hash": "route-secondary-test-hash",
            "player_id": str(player[0])
        }
    )

    assert response.status_code == 302
    assert (
        response.headers["Location"]
        .endswith("/admin/dink_identities")
    )

    primary_identity = database.get_dink_identity_by_hash(
        "route-primary-test-hash"
    )

    secondary_identity = database.get_dink_identity_by_hash(
        "route-secondary-test-hash"
    )

    assert primary_identity is not None
    assert primary_identity[1] == player[0]
    assert primary_identity[3] == "LINKED"

    assert secondary_identity is not None
    assert secondary_identity[1] is None
    assert secondary_identity[3] == "PENDING"


def test_pending_event_review_preserves_conflicting_claimed_rsns(client):
    create_test_player(
        "Real Review Tester",
        team_name="Conflict Review Team"
    )

    first_result = ingest_observation(
        "Real Review Tester",
        "conflict-review-event-hash",
        "Goblin"
    )

    second_result = ingest_observation(
        "Wrong Review Name",
        "conflict-review-event-hash",
        "Man"
    )

    player = database.get_player_by_name(
        "Real Review Tester"
    )

    link_result = database.manually_link_dink_identity(
        "conflict-review-event-hash",
        player[0]
    )

    assert first_result["status"] == "PENDING"
    assert second_result["status"] == "CONFLICT"
    assert link_result["status"] == "LINKED"

    review_rows = database.get_pending_dink_event_review_rows()

    assert len(review_rows) == 2

    assert review_rows[0][0] == first_result["event_id"]
    assert review_rows[0][2] == "Real Review Tester"
    assert review_rows[0][3] == "KILL_COUNT"
    assert review_rows[0][7] == "LINKED"
    assert review_rows[0][8] == "Real Review Tester"
    assert review_rows[0][9] == player[0]
    assert review_rows[0][10] == "Real Review Tester"
    assert review_rows[0][11] == "Conflict Review Team"

    assert review_rows[1][0] == second_result["event_id"]
    assert review_rows[1][2] == "Wrong Review Name"
    assert review_rows[1][3] == "KILL_COUNT"
    assert review_rows[1][7] == "LINKED"
    assert review_rows[1][8] == "Real Review Tester"
    assert review_rows[1][9] == player[0]
    assert review_rows[1][10] == "Real Review Tester"
    assert review_rows[1][11] == "Conflict Review Team"


def test_reject_pending_dink_event_marks_event_rejected(client):
    create_test_player(
        "Reject Tester",
        team_name="Reject Test Team"
    )

    ingest_result = ingest_observation(
        "Reject Tester",
        "reject-test-hash",
        "Goblin"
    )

    assert ingest_result["status"] == "PENDING"

    reject_result = database.reject_pending_dink_event(
        event_id=ingest_result["event_id"],
        review_source="WEB",
        reviewer_id=123,
        reviewer_name="Reject Test Admin",
        reason=(
            "Screenshot does not clearly show the drop."
        )
    )

    assert reject_result["status"] == "REJECTED"

    event = database.get_dink_event_by_id(
        ingest_result["event_id"]
    )

    assert event is not None
    assert event[5] is None
    assert event[10] == "REJECTED"
    assert event[12] is not None

    decision = database.get_staff_review_decision(
        "DINK_EVENT",
        ingest_result["event_id"]
    )

    assert decision is not None
    assert decision[1] == "DINK_EVENT"
    assert decision[2] == ingest_result["event_id"]
    assert decision[3] == "REJECT"
    assert decision[4] == "WEB"
    assert decision[5] == 123
    assert decision[6] == "Reject Test Admin"
    assert decision[7] == (
        "Screenshot does not clearly show the drop."
    )
    assert decision[8] is not None

    review_rows = database.get_pending_dink_event_review_rows()

    assert review_rows == []


def test_admin_can_view_historical_dink_event_review(client):
    create_test_player(
        "Historical Review Tester",
        team_name="Historical Review Team"
    )

    first_result = ingest_observation(
        "Historical Review Tester",
        "historical-review-test-hash",
        "Goblin"
    )

    second_result = ingest_observation(
        "Wrong Historical Name",
        "historical-review-test-hash",
        "Man"
    )

    player = database.get_player_by_name(
        "Historical Review Tester"
    )

    link_result = database.manually_link_dink_identity(
        "historical-review-test-hash",
        player[0]
    )

    assert first_result["status"] == "PENDING"
    assert second_result["status"] == "CONFLICT"
    assert link_result["status"] == "LINKED"

    login_admin(client)

    response = client.get(
        "/admin/dink_events"
    )

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert "Historical Dink Event Review" in page
    assert "#1" in page
    assert "#2" in page
    assert "KILL_COUNT" in page
    assert "Historical Review Tester" in page
    assert "Wrong Historical Name" in page
    assert "RSN mismatch" in page
    assert "LINKED" in page
    assert "Ready for staff decision" in page
    assert "Historical Review Team" in page
    assert "historical-review-test-hash" in page


def test_admin_can_reject_historical_dink_event(client):
    create_test_player(
        "Admin Reject Tester",
        team_name="Admin Reject Team"
    )

    ingest_result = ingest_observation(
        "Admin Reject Tester",
        "admin-reject-test-hash",
        "Goblin"
    )

    event_id = ingest_result["event_id"]

    assert ingest_result["status"] == "PENDING"

    login_admin(client)

    response = client.post(
        "/admin/dink_events",
        data={
            "action": "reject_event",
            "event_id": str(event_id)
        },
        follow_redirects=True
    )

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert (
        f"Dink event #{event_id} was rejected."
        in page
    )

    event = database.get_dink_event_by_id(
        event_id
    )

    assert event is not None
    assert event[5] is None
    assert event[10] == "REJECTED"
    assert event[12] is not None

    review_rows = (
        database.get_pending_dink_event_review_rows()
    )

    assert review_rows == []


def test_admin_can_accept_historical_dink_event(client):
    create_test_player(
        "Admin Accept Tester",
        team_name="Admin Accept Team"
    )

    tile_id = database.add_tile_with_conditions(
        tile_name="Historical Accept Drop Test",
        tile_points=1,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Historical Accept Drop",
                "target": 1
            }
        ]
    )

    ingest_result = dink.ingest_dink_event(
        {
            "playerName": "Admin Accept Tester",
            "dinkAccountHash": "admin-accept-test-hash",
            "type": "LOOT",
            "extra": {
                "items": [
                    {
                        "name": "Historical Accept Drop",
                        "quantity": 1
                    }
                ]
            }
        }
    )

    event_id = ingest_result["event_id"]

    assert ingest_result["status"] == "PENDING"

    player = database.get_player_by_name(
        "Admin Accept Tester"
    )

    link_result = database.manually_link_dink_identity(
        "admin-accept-test-hash",
        player[0]
    )

    assert link_result["status"] == "LINKED"

    event_before = database.get_dink_event_by_id(
        event_id
    )

    assert event_before[10] == "PENDING_IDENTITY"
    assert event_before[5] is None

    login_admin(client)

    response = client.post(
        "/admin/dink_events",
        data={
            "action": "accept_event",
            "event_id": str(event_id)
        },
        follow_redirects=True
    )

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert (
        f"Dink event #{event_id} was accepted and processed."
        in page
    )

    event_after = database.get_dink_event_by_id(
        event_id
    )

    assert event_after is not None
    assert event_after[5] == player[0]
    assert event_after[10] == "PROCESSED"
    assert event_after[12] is not None

    audit_rows = (
        database.get_dink_event_progress_by_event_id(
            event_id
        )
    )

    assert len(audit_rows) == 1

    team = database.get_team_by_name(
        "Admin Accept Team"
    )

    completed_tiles = (
        database.get_completed_tiles_by_team_id_and_tile_id(
            team[3],
            tile_id
        )
    )

    assert len(completed_tiles) == 1

    admin_user = database.get_user_by_email(
        "identity-admin@example.test"
    )

    assert admin_user is not None

    decision = database.get_staff_review_decision(
        "DINK_EVENT",
        event_id
    )

    assert decision is not None
    assert decision[1] == "DINK_EVENT"
    assert decision[2] == event_id
    assert decision[3] == "ACCEPT"
    assert decision[4] == "WEB"
    assert decision[5] == admin_user.id
    assert decision[6] == "Identity Admin"
    assert decision[7] is None
    assert decision[8] is not None

    review_rows = (
        database.get_pending_dink_event_review_rows()
    )

    assert review_rows == []


def test_admin_cannot_accept_unlinked_historical_dink_event(client):
    create_test_player(
        "Unlinked Accept Tester",
        team_name="Unlinked Accept Team"
    )

    ingest_result = dink.ingest_dink_event(
        {
            "playerName": "Unlinked Accept Tester",
            "dinkAccountHash": "unlinked-accept-test-hash",
            "type": "LOOT",
            "extra": {
                "items": [
                    {
                        "name": "Unlinked Accept Drop",
                        "quantity": 1
                    }
                ]
            }
        }
    )

    event_id = ingest_result["event_id"]

    assert ingest_result["status"] == "PENDING"

    login_admin(client)

    response = client.post(
        "/admin/dink_events",
        data={
            "action": "accept_event",
            "event_id": str(event_id)
        },
        follow_redirects=True
    )

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert (
        "This Dink event cannot be accepted "
        "until its identity is linked."
        in page
    )

    event = database.get_dink_event_by_id(
        event_id
    )

    assert event is not None
    assert event[5] is None
    assert event[10] == "PENDING_IDENTITY"
    assert event[12] is None

    audit_rows = (
        database.get_dink_event_progress_by_event_id(
            event_id
        )
    )

    assert audit_rows == []


def test_admin_can_view_dink_event_screenshot(client):
    create_test_player(
        "Screenshot Tester"
    )

    ingest_result = ingest_observation(
        "Screenshot Tester",
        "screenshot-test-hash",
        "Goblin"
    )

    event_id = ingest_result["event_id"]

    screenshot_directory = (
        PROJECT_ROOT
        / "uploads"
        / "dink_evidence"
    )

    screenshot_directory.mkdir(
        parents=True,
        exist_ok=True
    )

    screenshot_file = (
        screenshot_directory
        / f"dink_event_{event_id}.png"
    )

    screenshot_file.unlink(
        missing_ok=True
    )

    response = None
    try:
        screenshot_file.write_bytes(
            b"DanBot screenshot regression test"
        )

        relative_path = (
            f"uploads/dink_evidence/"
            f"dink_event_{event_id}.png"
        )

        database.update_dink_event_screenshot(
            event_id,
            relative_path,
            "test-screenshot-sha256"
        )

        login_admin(client)

        response = client.get(
            f"/admin/dink_event/"
            f"{event_id}/screenshot"
        )

        assert response.status_code == 200
        assert (
            response.data
            == b"DanBot screenshot regression test"
        )

    finally:
        if response is not None:
            response.close()

        screenshot_file.unlink(
            missing_ok=True
        )


def test_dink_event_screenshot_rejects_path_outside_evidence_directory(
    client
):
    create_test_player(
        "Screenshot Path Tester"
    )

    ingest_result = ingest_observation(
        "Screenshot Path Tester",
        "screenshot-path-test-hash",
        "Goblin"
    )

    event_id = ingest_result["event_id"]

    outside_file = (
        PROJECT_ROOT
        / "uploads"
        / f"dink_event_{event_id}.png"
    )

    outside_file.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    outside_file.unlink(
        missing_ok=True
    )

    response = None

    try:
        outside_file.write_bytes(
            b"This file must never be served"
        )

        unsafe_path = (
            f"uploads/dink_evidence/../"
            f"dink_event_{event_id}.png"
        )

        database.update_dink_event_screenshot(
            event_id,
            unsafe_path,
            "unsafe-test-sha256"
        )

        login_admin(client)

        response = client.get(
            f"/admin/dink_event/"
            f"{event_id}/screenshot"
        )

        assert response.status_code == 404

    finally:
        if response is not None:
            response.close()

        outside_file.unlink(
            missing_ok=True
        )


def test_non_admin_cannot_view_dink_event_screenshot(client):
    create_test_player(
        "Screenshot Access Tester"
    )

    ingest_result = ingest_observation(
        "Screenshot Access Tester",
        "screenshot-access-test-hash",
        "Goblin"
    )

    event_id = ingest_result["event_id"]

    screenshot_directory = (
        PROJECT_ROOT
        / "uploads"
        / "dink_evidence"
    )

    screenshot_directory.mkdir(
        parents=True,
        exist_ok=True
    )

    screenshot_file = (
        screenshot_directory
        / f"dink_event_{event_id}.png"
    )

    screenshot_file.unlink(
        missing_ok=True
    )

    response = None

    try:
        screenshot_file.write_bytes(
            b"Private screenshot test"
        )

        database.update_dink_event_screenshot(
            event_id,
            (
                f"uploads/dink_evidence/"
                f"dink_event_{event_id}.png"
            ),
            "access-test-sha256"
        )

        create_test_user(
            "Screenshot User",
            "screenshot-user@example.test",
            "test-password"
        )

        login_response = login_test_user(
            client,
            "screenshot-user@example.test",
            "test-password"
        )

        assert login_response.status_code == 302

        response = client.get(
            f"/admin/dink_event/"
            f"{event_id}/screenshot"
        )

        assert response.status_code == 403

    finally:
        if response is not None:
            response.close()

        screenshot_file.unlink(
            missing_ok=True
        )


def test_non_admin_cannot_access_dink_events(client):
    create_test_player(
        "Dink Event Access Tester"
    )

    ingest_result = ingest_observation(
        "Dink Event Access Tester",
        "dink-event-access-test-hash",
        "Goblin"
    )

    event_id = ingest_result["event_id"]

    assert ingest_result["status"] == "PENDING"

    create_test_user(
        "Dink Event User",
        "dink-event-user@example.test",
        "test-password"
    )

    login_response = login_test_user(
        client,
        "dink-event-user@example.test",
        "test-password"
    )

    assert login_response.status_code == 302

    get_response = client.get(
        "/admin/dink_events"
    )

    assert get_response.status_code == 403

    post_response = client.post(
        "/admin/dink_events",
        data={
            "action": "reject_event",
            "event_id": str(event_id)
        }
    )

    assert post_response.status_code == 403

    event = database.get_dink_event_by_id(
        event_id
    )

    assert event is not None
    assert event[5] is None
    assert event[10] == "PENDING_IDENTITY"
    assert event[12] is None

def test_non_admin_cannot_view_dink_identities(client):
    create_test_user(
        "Identity User",
        "identity-user@example.test",
        "test-password"
    )

    login_response = login_test_user(
        client,
        "identity-user@example.test",
        "test-password"
    )

    assert login_response.status_code == 302

    response = client.get(
        "/admin/dink_identities"
    )

    assert response.status_code == 403


def test_unauthenticated_user_cannot_view_dink_identities(
    client
):
    response = client.get(
        "/admin/dink_identities"
    )

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]