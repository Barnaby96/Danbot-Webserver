import os
import sys

import pytest

from routes import dink

sys.path.insert(0, os.path.abspath('..'))
from utils import database, db_entities
from main import create_app
from utils.spoofed_jsons import spoof_drop


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

def test_case_insensitivity(client):
    database.reset_tables()
    database.read_teams('test_csvs/default_team_1.csv')
    database.read_tiles('test_csvs/default_tiles_1.csv')


    json_data = spoof_drop.item_spoof_json("DaNbIs", "CoIn PoUcH", 1)
    result = dink.parse_loot(json_data, None)
    assert len(database.get_drops_by_item_name_and_team_id("COiN pOuCh", 1)) > 0
    assert result == True

def test_relevant_drop_occurred(client):
    database.reset_tables()
    database.read_teams('test_csvs/default_team_1.csv')
    database.read_tiles('test_csvs/default_tiles_1.csv')


    json_data = spoof_drop.item_spoof_json("Danbis", "Coin pouch", 1)
    result = dink.parse_loot(json_data, None)
    assert len(database.get_drops_by_item_name_and_team_id("Coin pouch", 1)) > 0
    assert result == True

def test_tile_completed(client):
    database.reset_tables()
    database.read_teams('test_csvs/default_team_1.csv')
    database.read_tiles('test_csvs/default_tiles_1.csv')

    json_data = spoof_drop.item_spoof_json("Danbis", "Coin pouch", 1)
    result = dink.parse_loot(json_data, None)
    assert result == True
    result = dink.parse_loot(json_data, None)
    assert result == True
    result = dink.parse_loot(json_data, None)
    assert result == True

    team = db_entities.Team(database.get_team_by_id(1))
    assert team.team_points == 1
    player = db_entities.Player(database.get_player_by_name("Danbis"))
    assert player.tiles_completed == 1

def test_complex_trigger_weights(client):
    database.reset_tables()
    database.read_teams('test_csvs/default_team_1.csv')
    database.read_tiles('test_csvs/default_tiles_1.csv')

    json_data = spoof_drop.item_spoof_json("Danbis", "Coins", 6)
    result = dink.parse_loot(json_data, None)
    assert result == True

    player = db_entities.Player(database.get_player_by_name("Danbis"))
    assert player.tiles_completed == 0

    partial = db_entities.PartialCompletion(database.get_partial_completions_by_player_id(player.player_id)[0])
    assert round(float(partial.partial_completion), 2) == 0.60

def test_multiple_completions(client):
    database.reset_tables()
    database.read_teams('test_csvs/default_team_1.csv')
    database.read_tiles('test_csvs/default_tiles_1.csv')

    json_data = spoof_drop.item_spoof_json(
        "Danbis",
        "Coins",
        10
    )
    result = dink.parse_loot(json_data, None)
    assert result is True

    player_danbis = db_entities.Player(
        database.get_player_by_name("Danbis")
    )
    player_deidera = db_entities.Player(
        database.get_player_by_name("Deidera")
    )
    team = db_entities.Team(
        database.get_team_by_id(1)
    )

    assert player_danbis.tiles_completed == 1
    assert player_deidera.tiles_completed == 0
    assert team.team_points == 1

    json_data = spoof_drop.item_spoof_json(
        "Danbis",
        "Coins",
        11
    )
    result = dink.parse_loot(json_data, None)
    assert result is True

    json_data = spoof_drop.item_spoof_json(
        "Deidera",
        "Bones",
        1
    )
    result = dink.parse_loot(json_data, None)
    assert result is True

    player_danbis = db_entities.Player(
        database.get_player_by_name("Danbis")
    )
    player_deidera = db_entities.Player(
        database.get_player_by_name("Deidera")
    )
    team = db_entities.Team(
        database.get_team_by_id(1)
    )

    assert player_danbis.tiles_completed == 1
    assert player_deidera.tiles_completed == 0
    assert team.team_points == 1

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

    completed_tiles = (
        database.get_completed_tiles_by_team_id_and_tile_id(
            1,
            2
        )
    )
    assert len(completed_tiles) == 1

def test_drops_shared_by_team(client):
    database.reset_tables()
    database.read_teams('test_csvs/default_team_1.csv')
    database.read_tiles('test_csvs/default_tiles_1.csv')

    json_data = spoof_drop.item_spoof_json("Danbis", "Coins", 5)
    result = dink.parse_loot(json_data, None)
    assert result == True

    json_data = spoof_drop.item_spoof_json("Deidera", "Coins", 5)
    result = dink.parse_loot(json_data, None)
    assert result == True

    player_danbis = db_entities.Player(database.get_player_by_name("Danbis"))
    player_deidera = db_entities.Player(database.get_player_by_name("Deidera"))
    assert player_danbis.tiles_completed == 0.5
    assert player_deidera.tiles_completed == 0.5
    assert len(database.get_partial_completions_by_player_id(player_danbis.player_id)) == 0
    assert len(database.get_partial_completions_by_player_id(player_deidera.player_id)) == 0
    team = db_entities.Team(database.get_team_by_id(1))
    assert team.team_points == 1

def test_collections(client):
    database.reset_tables()
    database.read_teams('test_csvs/default_team_1.csv')
    database.read_tiles('test_csvs/default_tiles_1.csv')

    json_data = spoof_drop.item_spoof_json(
        "Danbis",
        "Air Rune",
        1
    )
    result = dink.parse_loot(json_data, None)
    assert result is True

    player_danbis = db_entities.Player(
        database.get_player_by_name("Danbis")
    )
    assert round(player_danbis.tiles_completed, 2) == 0

    partial_danbis = db_entities.PartialCompletion(
        database.get_partial_completions_by_player_id(
            player_danbis.player_id
        )[0]
    )
    assert round(
        float(partial_danbis.partial_completion),
        2
    ) == round(1/3, 2)

    json_data = spoof_drop.item_spoof_json(
        "Deidera",
        "Iron bolts",
        1
    )
    result = dink.parse_loot(json_data, None)
    assert result is True

    player_deidera = db_entities.Player(
        database.get_player_by_name("Deidera")
    )
    assert round(player_deidera.tiles_completed, 2) == 0

    partial_deidera = db_entities.PartialCompletion(
        database.get_partial_completions_by_player_id(
            player_deidera.player_id
        )[0]
    )
    assert round(
        float(partial_deidera.partial_completion),
        2
    ) == round(1/3, 2)

    json_data = spoof_drop.item_spoof_json(
        "Danbis",
        "Bronze arrow",
        1
    )
    result = dink.parse_loot(json_data, None)
    assert result is True

    player_danbis = db_entities.Player(
        database.get_player_by_name("Danbis")
    )
    player_deidera = db_entities.Player(
        database.get_player_by_name("Deidera")
    )

    assert round(
        player_danbis.tiles_completed,
        2
    ) == round(2/3, 2)

    assert round(
        player_deidera.tiles_completed,
        2
    ) == round(1/3, 2)

    assert (
        len(
            database.get_partial_completions_by_player_id(
                player_danbis.player_id
            )
        )
        == 0
    )

    assert (
        len(
            database.get_partial_completions_by_player_id(
                player_deidera.player_id
            )
        )
        == 0
    )

    team = db_entities.Team(
        database.get_team_by_id(1)
    )
    assert team.team_points == 1

    for player_name, item_name in [
        ("Danbis", "Earth rune"),
        ("Deidera", "Fire rune"),
        ("Deidera", "Steel arrow"),
    ]:
        json_data = spoof_drop.item_spoof_json(
            player_name,
            item_name,
            1
        )
        result = dink.parse_loot(json_data, None)
        assert result is True

    player_danbis = db_entities.Player(
        database.get_player_by_name("Danbis")
    )
    player_deidera = db_entities.Player(
        database.get_player_by_name("Deidera")
    )

    assert round(
        player_danbis.tiles_completed,
        2
    ) == round(2/3, 2)

    assert round(
        player_deidera.tiles_completed,
        2
    ) == round(1/3, 2)

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

    team = db_entities.Team(
        database.get_team_by_id(1)
    )
    assert team.team_points == 1

    completed_tiles = (
        database.get_completed_tiles_by_team_id_and_tile_id(
            1,
            3
        )
    )
    assert len(completed_tiles) == 1

def test_cross_team_drops(client):
    database.reset_tables()
    database.read_teams('test_csvs/default_team_1.csv')
    database.read_tiles('test_csvs/default_tiles_1.csv')

    json_data = spoof_drop.item_spoof_json("Danbis", "Air Rune", 1)
    result = dink.parse_loot(json_data, None)
    assert result == True

    player_danbis = db_entities.Player(database.get_player_by_name("Danbis"))
    assert round(player_danbis.tiles_completed, 2) == 0
    partial_danbis = db_entities.PartialCompletion(database.get_partial_completions_by_player_id(player_danbis.player_id)[0])
    assert round(float(partial_danbis.partial_completion), 2) == round(1/3, 2)

    json_data = spoof_drop.item_spoof_json("Max uwu", "Iron bolts", 1)
    result = dink.parse_loot(json_data, None)
    assert result == True

    player_muwu = db_entities.Player(database.get_player_by_name("Max uwu"))
    partial_muwu = db_entities.PartialCompletion(database.get_partial_completions_by_player_id(player_muwu.player_id)[0])
    assert round(float(partial_muwu.partial_completion), 2) == round(1/3, 2)
    partial_danbis = db_entities.PartialCompletion(database.get_partial_completions_by_player_id(player_danbis.player_id)[0])
    assert round(float(partial_danbis.partial_completion), 2) == round(1/3, 2)

    json_data = spoof_drop.item_spoof_json("Danbis", "Bronze arrow", 1)
    result = dink.parse_loot(json_data, None)
    assert result == True

    partial_danbis = db_entities.PartialCompletion(database.get_partial_completions_by_player_id(player_danbis.player_id)[0])
    assert round(float(partial_danbis.partial_completion), 2) == round(2/3, 2)

    team_1 = db_entities.Team(database.get_team_by_id(1))
    assert team_1.team_points == 0

    team_2 = db_entities.Team(database.get_team_by_id(2))
    assert team_2.team_points == 0

    json_data = spoof_drop.item_spoof_json("Max uwu", "Coin pouch", 1)
    result = dink.parse_loot(json_data, None)
    assert result == True
    result = dink.parse_loot(json_data, None)
    assert result == True

    partial_muwu_1 = db_entities.PartialCompletion(database.get_partial_completions_by_player_id(player_muwu.player_id)[0])
    partial_muwu_2 = db_entities.PartialCompletion(database.get_partial_completions_by_player_id(player_muwu.player_id)[1])
    assert round(
        float(
            partial_muwu_1.partial_completion
            + partial_muwu_2.partial_completion
        ),
        2
    ) == round(1, 2)

    result = dink.parse_loot(json_data, None)
    assert result == True

    player_muwu = db_entities.Player(database.get_player_by_name("Max uwu"))
    partial_muwu = db_entities.PartialCompletion(database.get_partial_completions_by_player_id(player_muwu.player_id)[0])
    assert round(float(partial_muwu.partial_completion), 2) == round(1/3, 2)
    assert round(player_muwu.tiles_completed, 2) == 1

    team_2 = db_entities.Team(database.get_team_by_id(2))
    assert team_2.team_points == 1
