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