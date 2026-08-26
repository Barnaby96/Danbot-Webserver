import os
import sys
from pathlib import Path
import hashlib
import io
import json

import pytest
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from routes import dink
from utils import database, db_entities
from main import create_app


@pytest.fixture(autouse=True)
def dink_test_database():
    if os.getenv("PGDATABASE") != "danbot_test":
        pytest.fail(
            "Dink regression tests must only run against "
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


def test_dink_identity_links_after_three_distinct_events():
    database.add_team(
        "Dink Test Team",
        0,
        ""
    )

    team = db_entities.Team(
        database.get_team_by_name("Dink Test Team")
    )

    database.add_player(
        "Dink Tester",
        0,
        0,
        0,
        team.team_id,
        0
    )

    player = db_entities.Player(
        database.get_player_by_name("Dink Tester")
    )

    dink_account_hash = "test-dink-hash-001"

    payloads = [
        {
            "playerName": "Dink Tester",
            "dinkAccountHash": dink_account_hash,
            "type": "KILL_COUNT",
            "extra": {
                "boss": "Goblin",
                "killCount": 1
            }
        },
        {
            "playerName": "Dink Tester",
            "dinkAccountHash": dink_account_hash,
            "type": "KILL_COUNT",
            "extra": {
                "boss": "Man",
                "killCount": 1
            }
        },
        {
            "playerName": "Dink Tester",
            "dinkAccountHash": dink_account_hash,
            "type": "KILL_COUNT",
            "extra": {
                "boss": "Spider",
                "killCount": 1
            }
        }
    ]

    first_result = dink.ingest_dink_event(payloads[0])
    second_result = dink.ingest_dink_event(payloads[1])
    third_result = dink.ingest_dink_event(payloads[2])

    assert first_result["status"] == "PENDING"
    assert first_result["observations"] == 1
    assert first_result["player_id"] is None

    assert second_result["status"] == "PENDING"
    assert second_result["observations"] == 2
    assert second_result["player_id"] is None

    assert third_result["status"] == "LINKED"
    assert third_result["observations"] == 3
    assert third_result["player_id"] == player.player_id

    identity = database.get_dink_identity_by_hash(
        dink_account_hash
    )

    assert identity is not None
    assert identity[1] == player.player_id
    assert identity[2] == "Dink Tester"
    assert identity[3] == "LINKED"


def test_duplicate_event_does_not_count_towards_identity_linking():
    database.add_team(
        "Dink Test Team",
        0,
        ""
    )

    team = db_entities.Team(
        database.get_team_by_name("Dink Test Team")
    )

    database.add_player(
        "Dink Tester",
        0,
        0,
        0,
        team.team_id,
        0
    )

    dink_account_hash = "test-dink-hash-duplicate"

    first_payload = {
        "playerName": "Dink Tester",
        "dinkAccountHash": dink_account_hash,
        "type": "KILL_COUNT",
        "extra": {
            "boss": "Goblin",
            "killCount": 1
        }
    }

    second_payload = {
        "playerName": "Dink Tester",
        "dinkAccountHash": dink_account_hash,
        "type": "KILL_COUNT",
        "extra": {
            "boss": "Man",
            "killCount": 1
        }
    }

    first_result = dink.ingest_dink_event(first_payload)
    duplicate_result = dink.ingest_dink_event(first_payload)
    second_result = dink.ingest_dink_event(second_payload)

    assert first_result["status"] == "PENDING"
    assert first_result["observations"] == 1

    assert duplicate_result["status"] == "DUPLICATE"
    assert duplicate_result["player_id"] is None

    assert second_result["status"] == "PENDING"
    assert second_result["observations"] == 2

    identity = database.get_dink_identity_by_hash(
        dink_account_hash
    )

    assert identity is not None
    assert identity[1] is None
    assert identity[3] == "PENDING"


def test_dink_identity_conflicts_when_hash_changes_rsn():
    database.add_team(
        "Dink Test Team",
        0,
        ""
    )

    team = db_entities.Team(
        database.get_team_by_name("Dink Test Team")
    )

    database.add_player(
        "Dink Tester",
        0,
        0,
        0,
        team.team_id,
        0
    )

    dink_account_hash = "test-dink-hash-conflict"

    first_payload = {
        "playerName": "Dink Tester",
        "dinkAccountHash": dink_account_hash,
        "type": "KILL_COUNT",
        "extra": {
            "boss": "Goblin",
            "killCount": 1
        }
    }

    conflicting_payload = {
        "playerName": "Different RSN",
        "dinkAccountHash": dink_account_hash,
        "type": "KILL_COUNT",
        "extra": {
            "boss": "Man",
            "killCount": 1
        }
    }

    first_result = dink.ingest_dink_event(first_payload)
    conflict_result = dink.ingest_dink_event(
        conflicting_payload
    )

    assert first_result["status"] == "PENDING"
    assert conflict_result["status"] == "CONFLICT"
    assert conflict_result["player_id"] is None

    identity = database.get_dink_identity_by_hash(
        dink_account_hash
    )

    assert identity is not None
    assert identity[1] is None
    assert identity[2] == "Dink Tester"
    assert identity[3] == "CONFLICT"


def test_second_dink_hash_for_linked_player_conflicts():
    database.add_team(
        "Dink Test Team",
        0,
        ""
    )

    team = db_entities.Team(
        database.get_team_by_name("Dink Test Team")
    )

    database.add_player(
        "Dink Tester",
        0,
        0,
        0,
        team.team_id,
        0
    )

    first_hash = "test-dink-hash-primary"
    second_hash = "test-dink-hash-secondary"

    for boss in ("Goblin", "Man", "Spider"):
        result = dink.ingest_dink_event({
            "playerName": "Dink Tester",
            "dinkAccountHash": first_hash,
            "type": "KILL_COUNT",
            "extra": {
                "boss": boss,
                "killCount": 1
            }
        })

    assert result["status"] == "LINKED"

    first_second_hash_result = dink.ingest_dink_event({
        "playerName": "Dink Tester",
        "dinkAccountHash": second_hash,
        "type": "KILL_COUNT",
        "extra": {
            "boss": "Rat",
            "killCount": 1
        }
    })

    second_second_hash_result = dink.ingest_dink_event({
        "playerName": "Dink Tester",
        "dinkAccountHash": second_hash,
        "type": "KILL_COUNT",
        "extra": {
            "boss": "Cow",
            "killCount": 1
        }
    })

    third_second_hash_result = dink.ingest_dink_event({
        "playerName": "Dink Tester",
        "dinkAccountHash": second_hash,
        "type": "KILL_COUNT",
        "extra": {
            "boss": "Chicken",
            "killCount": 1
        }
    })

    assert first_second_hash_result["status"] == "PENDING"
    assert first_second_hash_result["observations"] == 1

    assert second_second_hash_result["status"] == "PENDING"
    assert second_second_hash_result["observations"] == 2

    assert third_second_hash_result["status"] == "CONFLICT"
    assert third_second_hash_result["observations"] == 3
    assert third_second_hash_result["player_id"] is None

    primary_identity = database.get_dink_identity_by_hash(
        first_hash
    )
    secondary_identity = database.get_dink_identity_by_hash(
        second_hash
    )

    assert primary_identity is not None
    assert primary_identity[3] == "LINKED"

    assert secondary_identity is not None
    assert secondary_identity[1] is None
    assert secondary_identity[3] == "CONFLICT"


def test_linked_dink_hash_survives_rsn_change():
    database.add_team(
        "Dink Test Team",
        0,
        ""
    )

    team = db_entities.Team(
        database.get_team_by_name("Dink Test Team")
    )

    database.add_player(
        "Dink Tester",
        0,
        0,
        0,
        team.team_id,
        0
    )

    player = db_entities.Player(
        database.get_player_by_name("Dink Tester")
    )

    dink_account_hash = "test-dink-hash-rsn-change"

    for boss in ("Goblin", "Man", "Spider"):
        result = dink.ingest_dink_event({
            "playerName": "Dink Tester",
            "dinkAccountHash": dink_account_hash,
            "type": "KILL_COUNT",
            "extra": {
                "boss": boss,
                "killCount": 1
            }
        })

    assert result["status"] == "LINKED"
    assert result["player_id"] == player.player_id

    renamed_result = dink.ingest_dink_event({
        "playerName": "Renamed Dink Tester",
        "dinkAccountHash": dink_account_hash,
        "type": "KILL_COUNT",
        "extra": {
            "boss": "Rat",
            "killCount": 1
        }
    })

    assert renamed_result["status"] == "LINKED"
    assert renamed_result["player_id"] == player.player_id
    assert renamed_result["observations"] == 4

    identity = database.get_dink_identity_by_hash(
        dink_account_hash
    )

    assert identity is not None
    assert identity[1] == player.player_id
    assert identity[2] == "Dink Tester"
    assert identity[3] == "LINKED"


def test_pending_relevant_drop_is_processed_when_identity_links():
    database.add_team(
        "Dink Test Team",
        0,
        ""
    )

    team = db_entities.Team(
        database.get_team_by_name("Dink Test Team")
    )

    database.add_player(
        "Dink Tester",
        0,
        0,
        0,
        team.team_id,
        0
    )

    tile_id = database.add_tile_with_conditions(
        tile_name="Retrospective Drop Test",
        tile_points=1,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Retrospective Test Drop",
                "target": 1
            }
        ]
    )

    dink_account_hash = "test-dink-hash-retrospective"

    drop_result = dink.ingest_dink_event({
        "playerName": "Dink Tester",
        "dinkAccountHash": dink_account_hash,
        "type": "LOOT",
        "extra": {
            "items": [
                {
                    "name": "Retrospective Test Drop",
                    "quantity": 1
                }
            ]
        }
    })

    second_result = dink.ingest_dink_event({
        "playerName": "Dink Tester",
        "dinkAccountHash": dink_account_hash,
        "type": "KILL_COUNT",
        "extra": {
            "boss": "Goblin",
            "killCount": 1
        }
    })

    third_result = dink.ingest_dink_event({
        "playerName": "Dink Tester",
        "dinkAccountHash": dink_account_hash,
        "type": "KILL_COUNT",
        "extra": {
            "boss": "Man",
            "killCount": 1
        }
    })

    assert drop_result["status"] == "PENDING"
    assert drop_result["observations"] == 1

    assert second_result["status"] == "PENDING"
    assert second_result["observations"] == 2

    assert third_result["status"] == "LINKED"
    assert third_result["observations"] == 3

    completed_tiles = (
        database.get_completed_tiles_by_team_id_and_tile_id(
            team.team_id,
            tile_id
        )
    )

    assert len(completed_tiles) == 1

    pending_events = database.get_pending_dink_events_by_hash(
        dink_account_hash
    )

    assert pending_events == []


def test_pending_irrelevant_event_is_ignored_when_identity_links():
    database.add_team(
        "Dink Test Team",
        0,
        ""
    )

    team = db_entities.Team(
        database.get_team_by_name("Dink Test Team")
    )

    database.add_player(
        "Dink Tester",
        0,
        0,
        0,
        team.team_id,
        0
    )

    player = db_entities.Player(
        database.get_player_by_name("Dink Tester")
    )

    dink_account_hash = "test-dink-hash-pending-ignored"

    first_payload = {
        "playerName": "Dink Tester",
        "dinkAccountHash": dink_account_hash,
        "type": "KILL_COUNT",
        "extra": {
            "boss": "Goblin",
            "killCount": 1
        }
    }

    first_result = dink.ingest_dink_event(first_payload)

    second_result = dink.ingest_dink_event({
        "playerName": "Dink Tester",
        "dinkAccountHash": dink_account_hash,
        "type": "KILL_COUNT",
        "extra": {
            "boss": "Man",
            "killCount": 1
        }
    })

    third_result = dink.ingest_dink_event({
        "playerName": "Dink Tester",
        "dinkAccountHash": dink_account_hash,
        "type": "KILL_COUNT",
        "extra": {
            "boss": "Spider",
            "killCount": 1
        }
    })

    assert first_result["status"] == "PENDING"
    assert second_result["status"] == "PENDING"
    assert third_result["status"] == "LINKED"

    first_fingerprint = dink.create_dink_event_fingerprint(
        first_payload
    )

    stored_event = (
        database.get_recent_dink_event_by_fingerprint(
            first_fingerprint
        )
    )

    assert stored_event is not None
    assert stored_event[0] == first_result["event_id"]
    assert stored_event[2] == "IGNORED"
    assert stored_event[3] == player.player_id
    assert stored_event[4] == dink_account_hash

    pending_events = database.get_pending_dink_events_by_hash(
        dink_account_hash
    )

    assert pending_events == []


def test_pending_relevant_pet_is_processed_when_identity_links():
    database.add_team(
        "Dink Test Team",
        0,
        ""
    )

    team = db_entities.Team(
        database.get_team_by_name("Dink Test Team")
    )

    database.add_player(
        "Dink Tester",
        0,
        0,
        0,
        team.team_id,
        0
    )

    tile_id = database.add_tile_with_conditions(
        tile_name="Retrospective Pet Test",
        tile_points=1,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "PET",
                "condition_trigger": "Retrospective Test Pet",
                "target": 1
            }
        ]
    )

    dink_account_hash = "test-dink-hash-retrospective-pet"

    pet_payload = {
        "playerName": "Dink Tester",
        "dinkAccountHash": dink_account_hash,
        "type": "PET",
        "extra": {
            "petName": "Retrospective Test Pet"
        }
    }

    pet_result = dink.ingest_dink_event(
        pet_payload
    )

    second_result = dink.ingest_dink_event({
        "playerName": "Dink Tester",
        "dinkAccountHash": dink_account_hash,
        "type": "KILL_COUNT",
        "extra": {
            "boss": "Goblin",
            "killCount": 1
        }
    })

    third_result = dink.ingest_dink_event({
        "playerName": "Dink Tester",
        "dinkAccountHash": dink_account_hash,
        "type": "KILL_COUNT",
        "extra": {
            "boss": "Man",
            "killCount": 1
        }
    })

    assert pet_result["status"] == "PENDING"
    assert pet_result["observations"] == 1

    assert second_result["status"] == "PENDING"
    assert second_result["observations"] == 2

    assert third_result["status"] == "LINKED"
    assert third_result["observations"] == 3

    completed_tiles = (
        database.get_completed_tiles_by_team_id_and_tile_id(
            team.team_id,
            tile_id
        )
    )

    assert len(completed_tiles) == 1

    pet_fingerprint = dink.create_dink_event_fingerprint(
        pet_payload
    )

    stored_event = (
        database.get_recent_dink_event_by_fingerprint(
            pet_fingerprint
        )
    )

    assert stored_event is not None
    assert stored_event[0] == pet_result["event_id"]
    assert stored_event[2] == "PROCESSED"


def test_linked_drop_processes_through_json_endpoint(
    client,
    monkeypatch
):
    database.add_team(
        "Dink Test Team",
        0,
        ""
    )

    team = db_entities.Team(
        database.get_team_by_name("Dink Test Team")
    )

    database.add_player(
        "Dink Tester",
        0,
        0,
        0,
        team.team_id,
        0
    )

    tile_id = database.add_tile_with_conditions(
        tile_name="Endpoint Drop Test",
        tile_points=1,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Endpoint Test Drop",
                "target": 1
            }
        ]
    )

    dink_account_hash = "test-dink-hash-endpoint-drop"

    for boss in ("Goblin", "Man", "Spider"):
        link_result = dink.ingest_dink_event({
            "playerName": "Dink Tester",
            "dinkAccountHash": dink_account_hash,
            "type": "KILL_COUNT",
            "extra": {
                "boss": boss,
                "killCount": 1
            }
        })

    assert link_result["status"] == "LINKED"

    monkeypatch.setenv(
        "TRACKING",
        "TRUE"
    )

    response = client.post(
        "/dink",
        json={
            "playerName": "Dink Tester",
            "dinkAccountHash": dink_account_hash,
            "type": "LOOT",
            "extra": {
                "items": [
                    {
                        "name": "Endpoint Test Drop",
                        "quantity": 1
                    }
                ]
            }
        }
    )

    assert response.status_code == 200

    response_data = response.get_json()

    assert response_data["message"] == "Dink event received"
    assert response_data["identity_status"] == "LINKED"
    assert response_data["observations"] == 4
    assert response_data["processing_status"] == "PROCESSED"

    completed_tiles = (
        database.get_completed_tiles_by_team_id_and_tile_id(
            team.team_id,
            tile_id
        )
    )

    assert len(completed_tiles) == 1


def test_linked_pet_processes_through_json_endpoint(
    client,
    monkeypatch
):
    database.add_team(
        "Dink Test Team",
        0,
        ""
    )

    team = db_entities.Team(
        database.get_team_by_name("Dink Test Team")
    )

    database.add_player(
        "Dink Tester",
        0,
        0,
        0,
        team.team_id,
        0
    )

    tile_id = database.add_tile_with_conditions(
        tile_name="Endpoint Pet Test",
        tile_points=1,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "PET",
                "condition_trigger": "Endpoint Test Pet",
                "target": 1
            }
        ]
    )

    dink_account_hash = "test-dink-hash-endpoint-pet"

    for boss in ("Goblin", "Man", "Spider"):
        link_result = dink.ingest_dink_event({
            "playerName": "Dink Tester",
            "dinkAccountHash": dink_account_hash,
            "type": "KILL_COUNT",
            "extra": {
                "boss": boss,
                "killCount": 1
            }
        })

    assert link_result["status"] == "LINKED"

    monkeypatch.setenv(
        "TRACKING",
        "TRUE"
    )

    response = client.post(
        "/dink",
        json={
            "playerName": "Dink Tester",
            "dinkAccountHash": dink_account_hash,
            "type": "PET",
            "extra": {
                "petName": "Endpoint Test Pet"
            }
        }
    )

    assert response.status_code == 200

    response_data = response.get_json()

    assert response_data["identity_status"] == "LINKED"
    assert response_data["observations"] == 4
    assert response_data["processing_status"] == "PROCESSED"

    completed_tiles = (
        database.get_completed_tiles_by_team_id_and_tile_id(
            team.team_id,
            tile_id
        )
    )

    assert len(completed_tiles) == 1


def test_irrelevant_linked_loot_is_ignored_through_endpoint(
    client,
    monkeypatch
):
    database.add_team(
        "Dink Test Team",
        0,
        ""
    )

    team = db_entities.Team(
        database.get_team_by_name("Dink Test Team")
    )

    database.add_player(
        "Dink Tester",
        0,
        0,
        0,
        team.team_id,
        0
    )

    dink_account_hash = "test-dink-hash-endpoint-ignored"

    for boss in ("Goblin", "Man", "Spider"):
        link_result = dink.ingest_dink_event({
            "playerName": "Dink Tester",
            "dinkAccountHash": dink_account_hash,
            "type": "KILL_COUNT",
            "extra": {
                "boss": boss,
                "killCount": 1
            }
        })

    assert link_result["status"] == "LINKED"

    monkeypatch.setenv(
        "TRACKING",
        "TRUE"
    )

    payload = {
        "playerName": "Dink Tester",
        "dinkAccountHash": dink_account_hash,
        "type": "LOOT",
        "extra": {
            "items": [
                {
                    "name": "Completely Irrelevant Drop",
                    "quantity": 1
                }
            ]
        }
    }

    response = client.post(
        "/dink",
        json=payload
    )

    assert response.status_code == 200

    response_data = response.get_json()

    assert response_data["identity_status"] == "LINKED"
    assert response_data["observations"] == 4
    assert response_data["processing_status"] == "IGNORED"

    fingerprint = dink.create_dink_event_fingerprint(
        payload
    )

    stored_event = (
        database.get_recent_dink_event_by_fingerprint(
            fingerprint
        )
    )

    assert stored_event is not None
    assert stored_event[0] == response_data["event_id"]
    assert stored_event[2] == "IGNORED"


def test_multi_item_loot_scores_all_relevant_items(
    client,
    monkeypatch
):
    database.add_team(
        "Dink Test Team",
        0,
        ""
    )

    team = db_entities.Team(
        database.get_team_by_name("Dink Test Team")
    )

    database.add_player(
        "Dink Tester",
        0,
        0,
        0,
        team.team_id,
        0
    )

    first_tile_id = database.add_tile_with_conditions(
        tile_name="Multi Item Drop A Tile",
        tile_points=1,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Multi Item Drop A",
                "target": 1
            }
        ]
    )

    second_tile_id = database.add_tile_with_conditions(
        tile_name="Multi Item Drop B Tile",
        tile_points=1,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Multi Item Drop B",
                "target": 2
            }
        ]
    )

    dink_account_hash = "test-dink-hash-multi-item"

    for boss in ("Goblin", "Man", "Spider"):
        link_result = dink.ingest_dink_event({
            "playerName": "Dink Tester",
            "dinkAccountHash": dink_account_hash,
            "type": "KILL_COUNT",
            "extra": {
                "boss": boss,
                "killCount": 1
            }
        })

    assert link_result["status"] == "LINKED"

    monkeypatch.setenv(
        "TRACKING",
        "TRUE"
    )

    response = client.post(
        "/dink",
        json={
            "playerName": "Dink Tester",
            "dinkAccountHash": dink_account_hash,
            "type": "LOOT",
            "extra": {
                "items": [
                    {
                        "name": "Multi Item Drop A",
                        "quantity": 1
                    },
                    {
                        "name": "Coins",
                        "quantity": 57
                    },
                    {
                        "name": "Multi Item Drop B",
                        "quantity": 2
                    }
                ]
            }
        }
    )

    assert response.status_code == 200

    response_data = response.get_json()

    assert response_data["identity_status"] == "LINKED"
    assert response_data["processing_status"] == "PROCESSED"

    first_completions = (
        database.get_completed_tiles_by_team_id_and_tile_id(
            team.team_id,
            first_tile_id
        )
    )

    second_completions = (
        database.get_completed_tiles_by_team_id_and_tile_id(
            team.team_id,
            second_tile_id
        )
    )

    assert len(first_completions) == 1
    assert len(second_completions) == 1

    audit_rows = database.get_dink_event_progress_by_event_id(
        response_data["event_id"]
    )

    assert len(audit_rows) == 2

    audit_triggers = {
        row[5]: row[6]
        for row in audit_rows
    }

    assert audit_triggers == {
        "Multi Item Drop A": 1,
        "Multi Item Drop B": 2
    }

    assert "Coins" not in audit_triggers


def test_duplicate_delivery_cannot_double_score(
    client,
    monkeypatch
):
    database.add_team(
        "Dink Test Team",
        0,
        ""
    )

    team = db_entities.Team(
        database.get_team_by_name("Dink Test Team")
    )

    database.add_player(
        "Dink Tester",
        0,
        0,
        0,
        team.team_id,
        0
    )

    tile_id = database.add_tile_with_conditions(
        tile_name="Duplicate Protection Test",
        tile_points=1,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Duplicate Test Drop",
                "target": 2
            }
        ]
    )

    dink_account_hash = "test-dink-hash-duplicate-score"

    for boss in ("Goblin", "Man", "Spider"):
        link_result = dink.ingest_dink_event({
            "playerName": "Dink Tester",
            "dinkAccountHash": dink_account_hash,
            "type": "KILL_COUNT",
            "extra": {
                "boss": boss,
                "killCount": 1
            }
        })

    assert link_result["status"] == "LINKED"

    monkeypatch.setenv(
        "TRACKING",
        "TRUE"
    )

    payload = {
        "playerName": "Dink Tester",
        "dinkAccountHash": dink_account_hash,
        "type": "LOOT",
        "extra": {
            "items": [
                {
                    "name": "Duplicate Test Drop",
                    "quantity": 1
                }
            ]
        }
    }

    first_response = client.post(
        "/dink",
        json=payload
    )

    duplicate_response = client.post(
        "/dink",
        json=payload
    )

    assert first_response.status_code == 200
    assert duplicate_response.status_code == 200

    first_data = first_response.get_json()
    duplicate_data = duplicate_response.get_json()

    assert first_data["identity_status"] == "LINKED"
    assert first_data["processing_status"] == "PROCESSED"

    assert duplicate_data["identity_status"] == "DUPLICATE"
    assert duplicate_data["processing_status"] is None

    completed_tiles = (
        database.get_completed_tiles_by_team_id_and_tile_id(
            team.team_id,
            tile_id
        )
    )

    assert completed_tiles == []

    first_audit_rows = (
        database.get_dink_event_progress_by_event_id(
            first_data["event_id"]
        )
    )

    duplicate_audit_rows = (
        database.get_dink_event_progress_by_event_id(
            duplicate_data["event_id"]
        )
    )

    assert len(first_audit_rows) == 1
    assert first_audit_rows[0][6] == 1

    assert duplicate_audit_rows == []


def test_stranded_received_event_recovers_on_retry(
    client,
    monkeypatch
):
    database.add_team(
        "Dink Test Team",
        0,
        ""
    )

    team = db_entities.Team(
        database.get_team_by_name("Dink Test Team")
    )

    database.add_player(
        "Dink Tester",
        0,
        0,
        0,
        team.team_id,
        0
    )

    player = db_entities.Player(
        database.get_player_by_name("Dink Tester")
    )

    tile_id = database.add_tile_with_conditions(
        tile_name="Retry Recovery Test",
        tile_points=1,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Retry Recovery Drop",
                "target": 1
            }
        ]
    )

    dink_account_hash = "test-dink-hash-retry-recovery"

    for boss in ("Goblin", "Man", "Spider"):
        link_result = dink.ingest_dink_event({
            "playerName": "Dink Tester",
            "dinkAccountHash": dink_account_hash,
            "type": "KILL_COUNT",
            "extra": {
                "boss": boss,
                "killCount": 1
            }
        })

    assert link_result["status"] == "LINKED"
    assert link_result["player_id"] == player.player_id

    payload = {
        "playerName": "Dink Tester",
        "dinkAccountHash": dink_account_hash,
        "type": "LOOT",
        "extra": {
            "items": [
                {
                    "name": "Retry Recovery Drop",
                    "quantity": 1
                }
            ]
        }
    }

    fingerprint = dink.create_dink_event_fingerprint(
        payload
    )

    stranded_event_id = database.add_dink_event(
        event_fingerprint=fingerprint,
        raw_payload=payload,
        dink_account_hash=dink_account_hash,
        player_name="Dink Tester",
        player_id=player.player_id,
        event_type="LOOT",
        status="RECEIVED"
    )

    monkeypatch.setenv(
        "TRACKING",
        "TRUE"
    )

    response = client.post(
        "/dink",
        json=payload
    )

    assert response.status_code == 200

    response_data = response.get_json()

    assert response_data["identity_status"] == "RETRY"
    assert response_data["processing_status"] == "PROCESSED"

    duplicate_event_id = response_data["event_id"]

    assert duplicate_event_id != stranded_event_id

    original_audit_rows = (
        database.get_dink_event_progress_by_event_id(
            stranded_event_id
        )
    )

    duplicate_audit_rows = (
        database.get_dink_event_progress_by_event_id(
            duplicate_event_id
        )
    )

    assert len(original_audit_rows) == 1
    assert original_audit_rows[0][5] == "Retry Recovery Drop"
    assert duplicate_audit_rows == []

    completed_tiles = (
        database.get_completed_tiles_by_team_id_and_tile_id(
            team.team_id,
            tile_id
        )
    )

    assert len(completed_tiles) == 1

    stored_original = (
        database.get_recent_dink_event_by_fingerprint(
            fingerprint
        )
    )

    assert stored_original is not None
    assert stored_original[0] == stranded_event_id
    assert stored_original[2] == "PROCESSED"
    assert stored_original[3] == player.player_id


def test_retry_after_recovered_event_becomes_duplicate(
    client,
    monkeypatch
):
    database.add_team(
        "Dink Test Team",
        0,
        ""
    )

    team = db_entities.Team(
        database.get_team_by_name("Dink Test Team")
    )

    database.add_player(
        "Dink Tester",
        0,
        0,
        0,
        team.team_id,
        0
    )

    player = db_entities.Player(
        database.get_player_by_name("Dink Tester")
    )

    tile_id = database.add_tile_with_conditions(
        tile_name="Recovered Retry Duplicate Test",
        tile_points=1,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Recovered Retry Drop",
                "target": 2
            }
        ]
    )

    dink_account_hash = "test-dink-hash-recovered-duplicate"

    for boss in ("Goblin", "Man", "Spider"):
        link_result = dink.ingest_dink_event({
            "playerName": "Dink Tester",
            "dinkAccountHash": dink_account_hash,
            "type": "KILL_COUNT",
            "extra": {
                "boss": boss,
                "killCount": 1
            }
        })

    assert link_result["status"] == "LINKED"

    payload = {
        "playerName": "Dink Tester",
        "dinkAccountHash": dink_account_hash,
        "type": "LOOT",
        "extra": {
            "items": [
                {
                    "name": "Recovered Retry Drop",
                    "quantity": 1
                }
            ]
        }
    }

    fingerprint = dink.create_dink_event_fingerprint(
        payload
    )

    stranded_event_id = database.add_dink_event(
        event_fingerprint=fingerprint,
        raw_payload=payload,
        dink_account_hash=dink_account_hash,
        player_name="Dink Tester",
        player_id=player.player_id,
        event_type="LOOT",
        status="RECEIVED"
    )

    monkeypatch.setenv(
        "TRACKING",
        "TRUE"
    )

    recovery_response = client.post(
        "/dink",
        json=payload
    )

    recovery_data = recovery_response.get_json()

    assert recovery_response.status_code == 200
    assert recovery_data["identity_status"] == "RETRY"
    assert recovery_data["processing_status"] == "PROCESSED"

    later_retry_response = client.post(
        "/dink",
        json=payload
    )

    later_retry_data = later_retry_response.get_json()

    assert later_retry_response.status_code == 200
    assert later_retry_data["identity_status"] == "DUPLICATE"
    assert later_retry_data["processing_status"] is None

    original_audit_rows = (
        database.get_dink_event_progress_by_event_id(
            stranded_event_id
        )
    )

    later_retry_audit_rows = (
        database.get_dink_event_progress_by_event_id(
            later_retry_data["event_id"]
        )
    )

    assert len(original_audit_rows) == 1
    assert later_retry_audit_rows == []

    completed_tiles = (
        database.get_completed_tiles_by_team_id_and_tile_id(
            team.team_id,
            tile_id
        )
    )

    assert completed_tiles == []


def test_dink_progress_transaction_rolls_back_on_error():
    database.add_team(
        "Dink Test Team",
        0,
        ""
    )

    team = db_entities.Team(
        database.get_team_by_name("Dink Test Team")
    )

    database.add_player(
        "Dink Tester",
        0,
        0,
        0,
        team.team_id,
        0
    )

    player = db_entities.Player(
        database.get_player_by_name("Dink Tester")
    )

    tile_id = database.add_tile_with_conditions(
        tile_name="Atomic Rollback Test",
        tile_points=1,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Atomic Test Drop",
                "target": 2
            }
        ]
    )

    dink_account_hash = "test-dink-hash-atomic"

    payload = {
        "playerName": "Dink Tester",
        "dinkAccountHash": dink_account_hash,
        "type": "LOOT",
        "extra": {
            "items": [
                {
                    "name": "Atomic Test Drop",
                    "quantity": 1
                }
            ]
        }
    }

    fingerprint = dink.create_dink_event_fingerprint(
        payload
    )

    event_id = database.add_dink_event(
        event_fingerprint=fingerprint,
        raw_payload=payload,
        dink_account_hash=dink_account_hash,
        player_name="Dink Tester",
        player_id=player.player_id,
        event_type="LOOT",
        status="RECEIVED"
    )

    event_progress = [
        {
            "condition_type": "DROP",
            "trigger": "Atomic Test Drop",
            "amount": 1
        },
        {
            "condition_type": "EXPERIENCE",
            "trigger": "Attack",
            "amount": 1
        }
    ]

    with pytest.raises(
        ValueError,
        match="Event progress can only be applied"
    ):
        database.process_dink_event_progress(
            event_id=event_id,
            player_id=player.player_id,
            event_progress=event_progress
        )

    condition_progress = (
        database.get_tile_condition_progress(
            team.team_id,
            tile_id
        )
    )

    assert len(condition_progress) == 1
    assert condition_progress[0][5] == 0

    audit_rows = database.get_dink_event_progress_by_event_id(
        event_id
    )

    assert audit_rows == []

    completed_tiles = (
        database.get_completed_tiles_by_team_id_and_tile_id(
            team.team_id,
            tile_id
        )
    )

    assert completed_tiles == []

    stored_event = (
        database.get_recent_dink_event_by_fingerprint(
            fingerprint
        )
    )

    assert stored_event is not None
    assert stored_event[0] == event_id
    assert stored_event[2] == "RECEIVED"
    assert stored_event[3] == player.player_id


def test_n_of_unique_does_not_count_same_item_twice(
    client,
    monkeypatch
):
    database.add_team(
        "Dink Test Team",
        0,
        ""
    )

    team = db_entities.Team(
        database.get_team_by_name("Dink Test Team")
    )

    database.add_player(
        "Dink Tester",
        0,
        0,
        0,
        team.team_id,
        0
    )

    tile_id = database.add_tile_with_conditions(
        tile_name="Unique N Of Test",
        tile_points=1,
        tile_rules="",
        conditions=[
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Royal Item A",
                "target": 1
            },
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Royal Item B",
                "target": 1
            },
            {
                "completion_path": 1,
                "condition_type": "DROP",
                "condition_trigger": "Royal Item C",
                "target": 1
            }
        ],
        completion_paths=[
            {
                "completion_path": 1,
                "route_mode": "N_OF",
                "route_target": 2,
                "require_unique": True
            }
        ]
    )

    dink_account_hash = "test-dink-hash-n-of-unique"

    for boss in ("Goblin", "Man", "Spider"):
        link_result = dink.ingest_dink_event({
            "playerName": "Dink Tester",
            "dinkAccountHash": dink_account_hash,
            "type": "KILL_COUNT",
            "extra": {
                "boss": boss,
                "killCount": 1
            }
        })

    assert link_result["status"] == "LINKED"

    monkeypatch.setenv(
        "TRACKING",
        "TRUE"
    )

    first_response = client.post(
        "/dink",
        json={
            "playerName": "Dink Tester",
            "dinkAccountHash": dink_account_hash,
            "type": "LOOT",
            "extra": {
                "items": [
                    {
                        "name": "Royal Item A",
                        "quantity": 2
                    }
                ]
            }
        }
    )

    assert first_response.status_code == 200

    first_data = first_response.get_json()

    assert first_data["processing_status"] == "PROCESSED"

    completed_after_first = (
        database.get_completed_tiles_by_team_id_and_tile_id(
            team.team_id,
            tile_id
        )
    )

    assert completed_after_first == []

    condition_progress = (
        database.get_tile_condition_progress(
            team.team_id,
            tile_id
        )
    )

    progress_by_trigger = {
        row[3]: row[5]
        for row in condition_progress
    }

    assert progress_by_trigger["Royal Item A"] == 2
    assert progress_by_trigger["Royal Item B"] == 0
    assert progress_by_trigger["Royal Item C"] == 0

    second_response = client.post(
        "/dink",
        json={
            "playerName": "Dink Tester",
            "dinkAccountHash": dink_account_hash,
            "type": "LOOT",
            "extra": {
                "items": [
                    {
                        "name": "Royal Item B",
                        "quantity": 1
                    }
                ]
            }
        }
    )

    assert second_response.status_code == 200

    second_data = second_response.get_json()

    assert second_data["processing_status"] == "PROCESSED"

    completed_after_second = (
        database.get_completed_tiles_by_team_id_and_tile_id(
            team.team_id,
            tile_id
        )
    )

    assert len(completed_after_second) == 1


def test_ignored_multipart_event_minimises_evidence(
    client,
    monkeypatch
):
    database.add_team(
        "Dink Test Team",
        0,
        ""
    )

    team = db_entities.Team(
        database.get_team_by_name("Dink Test Team")
    )

    database.add_player(
        "Dink Tester",
        0,
        0,
        0,
        team.team_id,
        0
    )

    dink_account_hash = "test-dink-hash-multipart-ignored"

    for boss in ("Goblin", "Man", "Spider"):
        link_result = dink.ingest_dink_event({
            "playerName": "Dink Tester",
            "dinkAccountHash": dink_account_hash,
            "type": "KILL_COUNT",
            "extra": {
                "boss": boss,
                "killCount": 1
            }
        })

    assert link_result["status"] == "LINKED"

    monkeypatch.setenv(
        "TRACKING",
        "TRUE"
    )

    payload = {
        "playerName": "Dink Tester",
        "dinkAccountHash": dink_account_hash,
        "type": "LOOT",
        "extra": {
            "items": [
                {
                    "name": "Irrelevant Screenshot Drop",
                    "quantity": 1
                }
            ]
        }
    }

    screenshot_bytes = b"fake png evidence bytes"

    expected_sha256 = hashlib.sha256(
        screenshot_bytes
    ).hexdigest()

    response = client.post(
        "/dink",
        data={
            "payload_json": json.dumps(payload),
            "file": (
                io.BytesIO(screenshot_bytes),
                "ignored-evidence.png"
            )
        },
        content_type="multipart/form-data"
    )

    assert response.status_code == 200

    response_data = response.get_json()

    assert response_data["identity_status"] == "LINKED"
    assert response_data["processing_status"] == "IGNORED"

    event_id = response_data["event_id"]

    stored_event = database.get_dink_event_by_id(
        event_id
    )

    assert stored_event is not None
    assert stored_event[0] == event_id
    assert stored_event[7] == {}
    assert stored_event[8] is None
    assert stored_event[9] == expected_sha256
    assert stored_event[10] == "IGNORED"

    expected_screenshot = (
        PROJECT_ROOT
        / "uploads"
        / "dink_evidence"
        / f"dink_event_{event_id}.png"
    )

    assert not expected_screenshot.exists()


def test_duplicate_receipt_is_minimised(
    client,
    monkeypatch
):
    database.add_team(
        "Dink Test Team",
        0,
        ""
    )

    team = db_entities.Team(
        database.get_team_by_name("Dink Test Team")
    )

    database.add_player(
        "Dink Tester",
        0,
        0,
        0,
        team.team_id,
        0
    )

    dink_account_hash = "test-dink-hash-duplicate-minimised"

    for boss in ("Goblin", "Man", "Spider"):
        link_result = dink.ingest_dink_event({
            "playerName": "Dink Tester",
            "dinkAccountHash": dink_account_hash,
            "type": "KILL_COUNT",
            "extra": {
                "boss": boss,
                "killCount": 1
            }
        })

    assert link_result["status"] == "LINKED"

    monkeypatch.setenv(
        "TRACKING",
        "TRUE"
    )

    payload = {
        "playerName": "Dink Tester",
        "dinkAccountHash": dink_account_hash,
        "type": "LOOT",
        "extra": {
            "items": [
                {
                    "name": "Duplicate Minimisation Drop",
                    "quantity": 1
                }
            ]
        }
    }

    screenshot_bytes = b"duplicate screenshot bytes"

    first_response = client.post(
        "/dink",
        data={
            "payload_json": json.dumps(payload),
            "file": (
                io.BytesIO(screenshot_bytes),
                "duplicate-evidence.png"
            )
        },
        content_type="multipart/form-data"
    )

    duplicate_response = client.post(
        "/dink",
        data={
            "payload_json": json.dumps(payload),
            "file": (
                io.BytesIO(screenshot_bytes),
                "duplicate-evidence.png"
            )
        },
        content_type="multipart/form-data"
    )

    assert first_response.status_code == 200
    assert duplicate_response.status_code == 200

    first_data = first_response.get_json()
    duplicate_data = duplicate_response.get_json()

    assert first_data["processing_status"] == "IGNORED"

    assert duplicate_data["identity_status"] == "DUPLICATE"
    assert duplicate_data["processing_status"] is None

    first_event = database.get_dink_event_by_id(
        first_data["event_id"]
    )

    duplicate_event = database.get_dink_event_by_id(
        duplicate_data["event_id"]
    )

    assert first_event is not None
    assert duplicate_event is not None

    assert first_event[7] == {}
    assert first_event[8] is None
    assert first_event[10] == "IGNORED"

    assert duplicate_event[2] == first_data["event_id"]
    assert duplicate_event[7] == {}
    assert duplicate_event[8] is None
    assert duplicate_event[10] == "IGNORED"


def test_dink_event_fingerprint_is_canonical_and_includes_screenshot():
    first_payload = {
        "playerName": "Dink Tester",
        "dinkAccountHash": "test-dink-hash-fingerprint",
        "type": "LOOT",
        "extra": {
            "items": [
                {
                    "name": "Fingerprint Test Drop",
                    "quantity": 1
                }
            ]
        }
    }

    reordered_payload = {
        "extra": {
            "items": [
                {
                    "quantity": 1,
                    "name": "Fingerprint Test Drop"
                }
            ]
        },
        "type": "LOOT",
        "dinkAccountHash": "test-dink-hash-fingerprint",
        "playerName": "Dink Tester"
    }

    screenshot_sha256 = hashlib.sha256(
        b"first screenshot"
    ).hexdigest()

    different_screenshot_sha256 = hashlib.sha256(
        b"different screenshot"
    ).hexdigest()

    first_fingerprint = dink.create_dink_event_fingerprint(
        first_payload,
        screenshot_sha256
    )

    reordered_fingerprint = dink.create_dink_event_fingerprint(
        reordered_payload,
        screenshot_sha256
    )

    different_screenshot_fingerprint = (
        dink.create_dink_event_fingerprint(
            first_payload,
            different_screenshot_sha256
        )
    )

    assert first_fingerprint == reordered_fingerprint
    assert (
        first_fingerprint
        != different_screenshot_fingerprint
    )