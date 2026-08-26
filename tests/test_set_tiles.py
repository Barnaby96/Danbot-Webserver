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
    database.read_tiles('test_csvs/default_tiles_2.csv')

    json_data = spoof_drop.item_spoof_json("DanBis", "OdiUm 1", 1)
    result = dink.parse_loot(json_data, None)
    assert result == True

    player = db_entities.Player(database.get_player_by_name("Danbis"))
    assert round(player.tiles_completed, 2) == 0

    partial_danbis = db_entities.PartialCompletion(database.get_partial_completions_by_player_id(player.player_id)[0])
    assert round(float(partial_danbis.partial_completion), 2) == round(1/3, 2)

    team = db_entities.Team(database.get_team_by_id(1))
    assert team.team_points == 0


def test_single_set_piece(client):
    database.reset_tables()
    database.read_teams('test_csvs/default_team_1.csv')
    database.read_tiles('test_csvs/default_tiles_2.csv')

    json_data = spoof_drop.item_spoof_json("Danbis", "Odium 1", 1)
    result = dink.parse_loot(json_data, None)
    assert result == True

    player = db_entities.Player(database.get_player_by_name("Danbis"))
    assert round(player.tiles_completed, 2) == 0

    partial_danbis = db_entities.PartialCompletion(database.get_partial_completions_by_player_id(player.player_id)[0])
    assert round(float(partial_danbis.partial_completion), 2) == round(1/3, 2)

    team = db_entities.Team(database.get_team_by_id(1))
    assert team.team_points == 0


def test_standard_completion(client):
    database.reset_tables()
    database.read_teams('test_csvs/default_team_1.csv')
    database.read_tiles('test_csvs/default_tiles_2.csv')

    json_data = spoof_drop.item_spoof_json("Danbis", "Odium 1", 1)
    result = dink.parse_loot(json_data, None)
    assert result == True

    json_data = spoof_drop.item_spoof_json("Danbis", "Odium 2", 1)
    result = dink.parse_loot(json_data, None)
    assert result == True

    json_data = spoof_drop.item_spoof_json("Danbis", "Odium 3", 1)
    result = dink.parse_loot(json_data, None)
    assert result == True

    player = db_entities.Player(database.get_player_by_name("Danbis"))
    assert player.tiles_completed == 1

    team = db_entities.Team(database.get_team_by_id(1))
    assert team.team_points == 1

def test_cross_team_completion_failure(client):
    database.reset_tables()
    database.read_teams('test_csvs/default_team_1.csv')
    database.read_tiles('test_csvs/default_tiles_2.csv')

    json_data = spoof_drop.item_spoof_json("Danbis", "Odium 1", 1)
    result = dink.parse_loot(json_data, None)
    assert result == True

    json_data = spoof_drop.item_spoof_json("Max uwu", "Odium 2", 1)
    result = dink.parse_loot(json_data, None)
    assert result == True

    json_data = spoof_drop.item_spoof_json("Danbis", "Odium 3", 1)
    result = dink.parse_loot(json_data, None)
    assert result == True

    player = db_entities.Player(database.get_player_by_name("Danbis"))
    partial_danbis = db_entities.PartialCompletion(database.get_partial_completions_by_player_id(player.player_id)[0])
    assert round(float(partial_danbis.partial_completion), 2) == round(2/3, 2)

    team = db_entities.Team(database.get_team_by_id(1))
    assert team.team_points == 0

def test_overcompletion(client):
    database.reset_tables()
    database.read_teams('test_csvs/default_team_1.csv')
    database.read_tiles('test_csvs/default_tiles_2.csv')

    json_data = spoof_drop.item_spoof_json("Danbis", "Odium 1", 1)
    result = dink.parse_loot(json_data, None)
    assert result == True

    json_data = spoof_drop.item_spoof_json("Danbis", "Odium 2", 1)
    result = dink.parse_loot(json_data, None)
    assert result == True

    json_data = spoof_drop.item_spoof_json("Danbis", "Odium 3", 1)
    result = dink.parse_loot(json_data, None)
    assert result == True

    player = db_entities.Player(database.get_player_by_name("Danbis"))
    assert player.tiles_completed == 1

    team = db_entities.Team(database.get_team_by_id(1))
    assert team.team_points == 1

    json_data = spoof_drop.item_spoof_json("Danbis", "Odium 1", 1)
    result = dink.parse_loot(json_data, None)
    assert result == True

    json_data = spoof_drop.item_spoof_json("Danbis", "Odium 2", 1)
    result = dink.parse_loot(json_data, None)
    assert result == True

    json_data = spoof_drop.item_spoof_json("Danbis", "Odium 3", 1)
    result = dink.parse_loot(json_data, None)
    assert result == True

    player = db_entities.Player(database.get_player_by_name("Danbis"))
    assert round(player.tiles_completed, 2) == 1

    team = db_entities.Team(database.get_team_by_id(1))
    assert team.team_points == 1


def test_mix_and_match_completion(client):
    database.reset_tables()
    database.read_teams('test_csvs/default_team_1.csv')
    database.read_tiles('test_csvs/default_tiles_2.csv')

    json_data = spoof_drop.item_spoof_json("Danbis", "Odium 1", 1)
    result = dink.parse_loot(json_data, None)
    assert result == True

    json_data = spoof_drop.item_spoof_json("Danbis", "Mal 2", 1)
    result = dink.parse_loot(json_data, None)
    assert result == True

    json_data = spoof_drop.item_spoof_json("Danbis", "Odium 3", 1)
    result = dink.parse_loot(json_data, None)
    assert result == True

    player = db_entities.Player(database.get_player_by_name("Danbis"))
    assert player.tiles_completed == 0
    partial_danbis = db_entities.PartialCompletion(database.get_partial_completions_by_player_id(player.player_id)[0])
    assert round(float(partial_danbis.partial_completion), 2) == round(1, 2)

    team = db_entities.Team(database.get_team_by_id(1))
    assert team.team_points == 0