import pytest

from utils import database, db_entities
from main import create_app
from routes import dink
from utils.spoofed_jsons.spoof_pet import spoof_pet


@pytest.fixture()
def app():
    app = create_app()
    # other setup can go here
    database.reset_tables()
    yield app
    # clean up / reset resources here

@pytest.fixture()
def client(app):
    return app.test_client()

def test_two_pet_drops(client):
    database.reset_tables()
    database.read_teams('test_csvs/default_team_1.csv')

    json_data = spoof_pet("Danbis", "Lil-zuk")
    result = dink.parse_pet(json_data, None)

    assert result == True

    team = database.get_team_by_id(1)
    team = db_entities.Team(team)
    assert round(team.team_points, 2) == round(0.5, 2)

    player_danbis = database.get_player_by_name("Danbis")
    player_danbis = db_entities.Player(player_danbis)
    assert round(player_danbis.tiles_completed, 2) == round(1, 2)
    assert player_danbis.pet_count == 1

    json_data = spoof_pet("Danbis", "Lil-ryguy")
    result = dink.parse_pet(json_data, None)

    assert result == True

    team = database.get_team_by_id(1)
    team = db_entities.Team(team)
    player_danbis = database.get_player_by_name("Danbis")
    player_danbis = db_entities.Player(player_danbis)
    assert round(team.team_points, 2) == round(1, 2)
    assert player_danbis.pet_count == 2

    player_danbis = database.get_player_by_name("Danbis")
    player_danbis = db_entities.Player(player_danbis)
    assert round(player_danbis.tiles_completed, 2) == round(2, 2)

def test_single_pet_drop(client):
    database.reset_tables()
    database.read_teams('test_csvs/default_team_1.csv')

    json_data = spoof_pet("Danbis", "Lil-zuk")
    result = dink.parse_pet(json_data, None)

    assert result == True

    team = database.get_team_by_id(1)
    team = db_entities.Team(team)
    assert round(team.team_points, 2) == round(0.5, 2)

    player_danbis = database.get_player_by_name("Danbis")
    player_danbis = db_entities.Player(player_danbis)
    assert player_danbis.tiles_completed == 1
    assert player_danbis.pet_count == 1

def test_two_pet_drops_different_players(client):
    database.reset_tables()
    database.read_teams('test_csvs/default_team_1.csv')

    json_data = spoof_pet("Danbis", "Lil-zuk")
    result = dink.parse_pet(json_data, None)
    assert result == True

    team = database.get_team_by_id(1)
    team = db_entities.Team(team)
    assert round(team.team_points, 2) == round(0.5, 2)

    player_danbis = database.get_player_by_name("Danbis")
    player_danbis = db_entities.Player(player_danbis)
    assert round(player_danbis.tiles_completed, 2) == round(1, 2)
    assert player_danbis.pet_count == 1

    json_data = spoof_pet("Deidera", "Lil-ryguy")
    result = dink.parse_pet(json_data, None)

    assert result == True

    team = database.get_team_by_id(1)
    team = db_entities.Team(team)
    assert round(team.team_points, 2) == round(1, 2)

    player_deidera = database.get_player_by_name("Deidera")
    player_deidera = db_entities.Player(player_deidera)
    assert round(player_deidera.tiles_completed, 2) == round(1, 2)
    assert player_deidera.pet_count == 1

def test_pet_tile_input_1(client):
    database.reset_tables()
    database.read_teams('test_csvs/default_team_1.csv')
    database.read_tiles('test_csvs/default_tiles_pet_1')

    json_data = spoof_pet("Danbis", "Skotizo")
    result = dink.parse_pet(json_data, None)
    assert result == True

    team = database.get_team_by_id(1)
    team = db_entities.Team(team)
    assert round(team.team_points, 2) == round(0, 2)

    json_data = spoof_pet("Danbis", "Lil-zuk")
    result = dink.parse_pet(json_data, None)
    assert result == True

    team = database.get_team_by_id(1)
    team = db_entities.Team(team)
    assert round(team.team_points, 2) == round(1, 2)

    json_data = spoof_pet("Danbis", "Lil-jad")
    result = dink.parse_pet(json_data, None)
    assert result == True

    team = database.get_team_by_id(1)
    team = db_entities.Team(team)
    assert round(team.team_points, 2) == round(1, 2)

def test_pet_tile_input_repetition(client):
    database.reset_tables()
    database.read_teams('test_csvs/default_team_1.csv')
    database.read_tiles('test_csvs/default_tiles_pet_repetition')

    # Skotizo is excluded by the PET tile trigger.
    json_data = spoof_pet(
        "Danbis",
        "Skotizo"
    )
    result = dink.parse_pet(
        json_data,
        None
    )
    assert result is True

    team = db_entities.Team(
        database.get_team_by_id(1)
    )
    assert round(team.team_points, 2) == 0

    # The first valid pet completes the tile.
    json_data = spoof_pet(
        "Danbis",
        "Lil-zuk"
    )
    result = dink.parse_pet(
        json_data,
        None
    )
    assert result is True

    team = db_entities.Team(
        database.get_team_by_id(1)
    )
    assert round(team.team_points, 2) == 1

    # Further valid pets cannot complete the same tile again.
    for pet_name in [
        "Lil-jad",
        "Lil-Dan",
        "Lil-Ryan",
    ]:
        json_data = spoof_pet(
            "Danbis",
            pet_name
        )
        result = dink.parse_pet(
            json_data,
            None
        )
        assert result is True

        team = db_entities.Team(
            database.get_team_by_id(1)
        )
        assert round(team.team_points, 2) == 1

    player = db_entities.Player(
        database.get_player_by_name("Danbis")
    )
    assert round(player.tiles_completed, 2) == 1

    completed_tiles = (
        database.get_completed_tiles_by_team_id_and_tile_id(
            1,
            4
        )
    )
    assert len(completed_tiles) == 1

def test_pet_tile_input_infinite(client):
    database.reset_tables()
    database.read_teams('test_csvs/default_team_1.csv')
    database.read_tiles('test_csvs/default_tiles_pet_infinite')

    team = db_entities.Team(
        database.get_team_by_id(1)
    )
    assert round(team.team_points, 2) == 0

    for i in range(10):
        json_data = spoof_pet(
            "Danbis",
            str(i)
        )
        result = dink.parse_pet(
            json_data,
            None
        )
        assert result is True

        team = db_entities.Team(
            database.get_team_by_id(1)
        )

        # The first valid pet completes the tile.
        # Later pets cannot score it again.
        assert round(team.team_points, 2) == 1

    player = db_entities.Player(
        database.get_player_by_name("Danbis")
    )
    assert round(player.tiles_completed, 2) == 1

    completed_tiles = (
        database.get_completed_tiles_by_team_id_and_tile_id(
            1,
            4
        )
    )
    assert len(completed_tiles) == 1