import pytest

from utils import database, db_entities
from main import create_app
from routes import dink
from utils.spoofed_jsons import spoof_chat


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

def test_single_chat_case_insensitivity(client):
    database.reset_tables()
    database.read_teams('test_csvs/default_team_1.csv')
    database.read_tiles('test_csvs/default_tiles_6.csv')

    json_data = spoof_chat.spoof_chat("Danbis", "YoU aRe ViCtOrIoUs!")
    result = dink.parse_chat(json_data, None)
    assert result == True

    player = database.get_player_by_name("Danbis")
    player = db_entities.Player(player)
    partial_player = db_entities.PartialCompletion(database.get_partial_completions_by_player_id(player.player_id)[0])
    assert round(float(partial_player.partial_completion), 2) == 1/5

def test_single_chat(client):
    database.reset_tables()
    database.read_teams('test_csvs/default_team_1.csv')
    database.read_tiles('test_csvs/default_tiles_6.csv')

    json_data = spoof_chat.spoof_chat("Danbis", "You are victorious!")
    result = dink.parse_chat(json_data, None)
    assert result == True

    player = database.get_player_by_name("Danbis")
    player = db_entities.Player(player)
    partial_player = db_entities.PartialCompletion(database.get_partial_completions_by_player_id(player.player_id)[0])
    assert round(float(partial_player.partial_completion), 2) == 1/5

def test_single_player_completion_chat(client):
    database.reset_tables()
    database.read_teams('test_csvs/default_team_1.csv')
    database.read_tiles('test_csvs/default_tiles_6.csv')

    player = database.get_player_by_name("Danbis")
    player = db_entities.Player(player)
    for i in range(5):
        json_data = spoof_chat.spoof_chat("Danbis", "You are victorious!")
        result = dink.parse_chat(json_data, None)
        assert result == True
        if i < 4:
            partial_player = db_entities.PartialCompletion(database.get_partial_completions_by_player_id(player.player_id)[0])
            assert round(float(partial_player.partial_completion), 2) == (i + 1) / 5
        else:
            assert len(database.get_partial_completions_by_player_id(player.player_id)) == 0

    team = database.get_team_by_id(player.team_id)
    team = db_entities.Team(team)
    assert team.team_points == 1

def test_multiplayer_completion_chat(client):
    database.reset_tables()
    database.read_teams('test_csvs/default_team_1.csv')
    database.read_tiles('test_csvs/default_tiles_6.csv')

    player_danbis = database.get_player_by_name("Danbis")
    player_danbis = db_entities.Player(player_danbis)
    for i in range(2):
        json_data = spoof_chat.spoof_chat("Danbis", "You are victorious!")
        result = dink.parse_chat(json_data, None)
        assert result == True

        if i < 4:
            partial_player = db_entities.PartialCompletion(
                database.get_partial_completions_by_player_id(player_danbis.player_id)[0])
            assert round(float(partial_player.partial_completion), 2) == (i + 1) / 5
        else:
            assert len(database.get_partial_completions_by_player_id(player_danbis.player_id)) == 0

    player_deidera = database.get_player_by_name("Deidera")
    player_deidera = db_entities.Player(player_deidera)
    for i in range(3):
        json_data = spoof_chat.spoof_chat("Deidera", "You are victorious!")
        result = dink.parse_chat(json_data, None)
        assert result == True

        if i < 2:
            partial_player = db_entities.PartialCompletion(
                database.get_partial_completions_by_player_id(player_deidera.player_id)[0])
            assert round(float(partial_player.partial_completion), 2) == (i + 1) / 5
        else:
            assert len(database.get_partial_completions_by_player_id(player_deidera.player_id)) == 0

    team = database.get_team_by_id(player_danbis.team_id)
    team = db_entities.Team(team)
    assert team.team_points == 1

def test_multiplayer_over_completion_chat(client):
    database.reset_tables()
    database.read_teams('test_csvs/default_team_1.csv')
    database.read_tiles('test_csvs/default_tiles_6.csv')

    player_danbis = db_entities.Player(
        database.get_player_by_name("Danbis")
    )

    for _ in range(5):
        json_data = spoof_chat.spoof_chat(
            "Danbis",
            "You are victorious!"
        )

        result = dink.parse_chat(
            json_data,
            None
        )

        assert result is True

    completed_tiles = (
        database.get_completed_tiles_by_team_id_and_tile_id(
            player_danbis.team_id,
            6
        )
    )

    assert len(completed_tiles) == 1

    team = db_entities.Team(
        database.get_team_by_id(
            player_danbis.team_id
        )
    )

    assert team.team_points == 1

    extra_result = dink.parse_chat(
        spoof_chat.spoof_chat(
            "Danbis",
            "You are victorious!"
        ),
        None
    )

    assert extra_result is False

    other_player_result = dink.parse_chat(
        spoof_chat.spoof_chat(
            "Deidera",
            "You are victorious!"
        ),
        None
    )

    assert other_player_result is False

    completed_tiles = (
        database.get_completed_tiles_by_team_id_and_tile_id(
            player_danbis.team_id,
            6
        )
    )

    assert len(completed_tiles) == 1

    team = db_entities.Team(
        database.get_team_by_id(
            player_danbis.team_id
        )
    )

    assert team.team_points == 1

    player_danbis = db_entities.Player(
        database.get_player_by_name("Danbis")
    )

    player_deidera = db_entities.Player(
        database.get_player_by_name("Deidera")
    )

    assert round(player_danbis.tiles_completed, 2) == 1
    assert round(player_deidera.tiles_completed, 2) == 0

    assert (
        database.get_partial_completions_by_player_id(
            player_danbis.player_id
        )
        == []
    )

    assert (
        database.get_partial_completions_by_player_id(
            player_deidera.player_id
        )
        == []
    )