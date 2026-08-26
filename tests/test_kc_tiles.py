import os
import sys

import pytest

from routes import dink

sys.path.insert(0, os.path.abspath('..'))
from utils import database, db_entities
from main import create_app
from utils.spoofed_jsons import spoof_kc


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
    database.read_tiles('test_csvs/default_tiles_6.csv')

    json_data = spoof_kc.kc_spoof_json("Danbis", "TzToK-JaD")
    result = dink.parse_kill_count(json_data, None)
    assert result == True

    player_danbis = db_entities.Player(database.get_player_by_name("DaNbIs"))

    partial_danbis = db_entities.PartialCompletion(
        database.get_partial_completions_by_player_id(player_danbis.player_id)[0])
    assert round(float(partial_danbis.partial_completion), 2) == round(1 / 9, 2)


def test_inferno_fire_cape(client):
    database.reset_tables()
    database.read_teams('test_csvs/default_team_1.csv')
    database.read_tiles('test_csvs/default_tiles_6.csv')

    json_data = spoof_kc.kc_spoof_json("Danbis", "TzTok-Jad")
    result = dink.parse_kill_count(json_data, None)
    assert result == True

    player_danbis = db_entities.Player(database.get_player_by_name("Danbis"))

    partial_danbis = db_entities.PartialCompletion(
        database.get_partial_completions_by_player_id(player_danbis.player_id)[0])
    assert round(float(partial_danbis.partial_completion), 2) == round(1 / 9, 2)
    # player_danbis = db_entities.Player(database.get_player_by_name("Danbis"))
    # assert round(player_danbis.tiles_completed, 2) == round(1/9, 2)

    json_data = spoof_kc.kc_spoof_json("Danbis", "TzTok-Zuk")
    result = dink.parse_kill_count(json_data, None)
    assert result == True

    # player_danbis = db_entities.Player(database.get_player_by_name("Danbis"))
    # assert round(player_danbis.tiles_completed, 2) == round(4/9, 2)
    partial_danbis = db_entities.PartialCompletion(
        database.get_partial_completions_by_player_id(player_danbis.player_id)[0])
    assert round(float(partial_danbis.partial_completion), 2) == round(4 / 9, 2)


def test_inferno_fire_over_partials_cape(client):
    database.reset_tables()
    database.read_teams('test_csvs/default_team_1.csv')
    database.read_tiles('test_csvs/default_tiles_6.csv')

    json_data = spoof_kc.kc_spoof_json("Danbis", "TzTok-Jad")
    result = dink.parse_kill_count(json_data, None)
    assert result == True

    player_danbis = db_entities.Player(database.get_player_by_name("Danbis"))

    partial_danbis = db_entities.PartialCompletion(
        database.get_partial_completions_by_player_id(player_danbis.player_id)[0])
    assert round(float(partial_danbis.partial_completion), 2) == round(1 / 9, 2)
    # player_danbis = db_entities.Player(database.get_player_by_name("Danbis"))
    # assert round(player_danbis.tiles_completed, 2) == round(1/9, 2)

    json_data = spoof_kc.kc_spoof_json("Danbis", "TzTok-Zuk")
    result = dink.parse_kill_count(json_data, None)
    assert result == True

    # player_danbis = db_entities.Player(database.get_player_by_name("Danbis"))
    # assert round(player_danbis.tiles_completed, 2) == round(4/9, 2)
    partial_danbis = db_entities.PartialCompletion(
        database.get_partial_completions_by_player_id(player_danbis.player_id)[0])
    assert round(float(partial_danbis.partial_completion), 2) == round(4 / 9, 2)

    json_data = spoof_kc.kc_spoof_json("Deidera", "TzTok-Zuk")
    result = dink.parse_kill_count(json_data, None)
    assert result == True

    player_deidera = db_entities.Player(database.get_player_by_name("Deidera"))
    # assert round(player_danbis.tiles_completed, 2) == round(4/9, 2)
    partial_deidera = db_entities.PartialCompletion(
        database.get_partial_completions_by_player_id(player_deidera.player_id)[0])
    assert round(float(partial_deidera.partial_completion), 2) == round(3 / 9, 2)

    json_data = spoof_kc.kc_spoof_json("Deidera", "TzTok-Zuk")
    result = dink.parse_kill_count(json_data, None)
    assert result == True

    player_deidera = db_entities.Player(database.get_player_by_name("Deidera"))
    player_danbis = db_entities.Player(database.get_player_by_name("Danbis"))

    assert len(database.get_partial_completions_by_player_id(player_danbis.player_id)) == 0
    assert len(
        database.get_partial_completions_by_player_id(
            player_deidera.player_id
        )
    ) == 0

    assert round(player_deidera.tiles_completed, 2) == round(5 / 9, 2)
    assert round(player_danbis.tiles_completed, 2) == round(4 / 9, 2)
    team = database.get_team_by_id(player_danbis.team_id)
    team = db_entities.Team(team)
    assert team.team_points == 1


def test_inferno_fire_cape_completion(client):
    database.reset_tables()
    database.read_teams('test_csvs/default_team_1.csv')
    database.read_tiles('test_csvs/default_tiles_6.csv')

    json_data = spoof_kc.kc_spoof_json("Danbis", "TzTok-Jad")
    result = dink.parse_kill_count(json_data, None)
    assert result == True

    player_danbis = db_entities.Player(database.get_player_by_name("Danbis"))

    partial_danbis = db_entities.PartialCompletion(
        database.get_partial_completions_by_player_id(player_danbis.player_id)[0])
    assert round(float(partial_danbis.partial_completion), 2) == round(1 / 9, 2)

    json_data = spoof_kc.kc_spoof_json("Danbis", "TzTok-Zuk")
    result = dink.parse_kill_count(json_data, None)
    assert result == True

    partial_danbis = db_entities.PartialCompletion(
        database.get_partial_completions_by_player_id(player_danbis.player_id)[0])
    assert round(float(partial_danbis.partial_completion), 2) == round(4 / 9, 2)

    json_data = spoof_kc.kc_spoof_json("Danbis", "TzTok-Zuk")
    result = dink.parse_kill_count(json_data, None)
    assert result == True

    partial_danbis = db_entities.PartialCompletion(
        database.get_partial_completions_by_player_id(player_danbis.player_id)[0])
    assert round(float(partial_danbis.partial_completion), 2) == round(7 / 9, 2)

    json_data = spoof_kc.kc_spoof_json("Danbis", "TzTok-Jad")
    result = dink.parse_kill_count(json_data, None)
    assert result == True

    partial_danbis = db_entities.PartialCompletion(
        database.get_partial_completions_by_player_id(player_danbis.player_id)[0])
    assert round(float(partial_danbis.partial_completion), 2) == round(8 / 9, 2)

    json_data = spoof_kc.kc_spoof_json("Danbis", "TzTok-Jad")
    result = dink.parse_kill_count(json_data, None)
    assert result == True

    assert len(database.get_partial_completions_by_player_id(player_danbis.player_id)) == 0
    player_danbis = db_entities.Player(database.get_player_by_name(player_danbis.player_name))
    assert player_danbis.tiles_completed == 1

    team = db_entities.Team(database.get_team_by_id(1))
    assert team.team_points == 1


def test_single_player_kc_completion(client):
    database.reset_tables()
    database.read_teams('test_csvs/default_team_1.csv')
    database.read_tiles('test_csvs/default_tiles_3.csv')

    player_danbis = db_entities.Player(database.get_player_by_name("Danbis"))
    for i in range(10):
        team = db_entities.Team(database.get_team_by_id(1))
        assert team.team_points == 0

        json_data = spoof_kc.kc_spoof_json("Danbis", "Vardorvis")
        result = dink.parse_kill_count(json_data, None)
        assert result == True

        if i < 9:
            partial_danbis = db_entities.PartialCompletion(
                database.get_partial_completions_by_player_id(player_danbis.player_id)[0])
            assert round(float(partial_danbis.partial_completion), 2) == round((i + 1) / 10, 2)
        else:
            assert len(database.get_partial_completions_by_player_id(player_danbis.player_id)) == 0

    player_danbis = db_entities.Player(database.get_player_by_name(player_danbis.player_name))
    assert round(player_danbis.tiles_completed, 2) == 1

    team = db_entities.Team(database.get_team_by_id(1))
    assert round(team.team_points, 2) == 1


def test_multiplayer_kc_completion(client):
    database.reset_tables()
    database.read_teams('test_csvs/default_team_1.csv')
    database.read_tiles('test_csvs/default_tiles_3.csv')

    player_deidera = db_entities.Player(database.get_player_by_name("Deidera"))
    player_danbis = db_entities.Player(database.get_player_by_name("Danbis"))

    for i in range(4):
        team = db_entities.Team(database.get_team_by_id(1))
        assert team.team_points == 0

        json_data = spoof_kc.kc_spoof_json("Danbis", "Vardorvis")
        result = dink.parse_kill_count(json_data, None)
        assert result == True

        partial_danbis = db_entities.PartialCompletion(
            database.get_partial_completions_by_player_id(player_danbis.player_id)[0])
        assert round(float(partial_danbis.partial_completion), 2) == round((i + 1) / 10, 2)

    for i in range(6):
        team = db_entities.Team(database.get_team_by_id(1))
        assert team.team_points == 0

        json_data = spoof_kc.kc_spoof_json("Deidera", "Vardorvis")
        result = dink.parse_kill_count(json_data, None)
        assert result == True

        if i < 5:
            partial_deidera = db_entities.PartialCompletion(
                database.get_partial_completions_by_player_id(player_deidera.player_id)[0])
            assert round(float(partial_deidera.partial_completion), 2) == round((i + 1) / 10, 2)
        else:
            assert len(database.get_partial_completions_by_player_id(player_danbis.player_id)) == 0
            assert len(database.get_partial_completions_by_player_id(player_deidera.player_id)) == 0

    team = db_entities.Team(database.get_team_by_id(1))
    assert team.team_points == 1


def test_multiple_completions(client):
    database.reset_tables()
    database.read_teams('test_csvs/default_team_1.csv')
    database.read_tiles('test_csvs/default_tiles_3.csv')

    player_danbis = db_entities.Player(
        database.get_player_by_name("Danbis")
    )

    # The first 10 kills should complete the tile once.
    for i in range(10):
        team = db_entities.Team(
            database.get_team_by_id(1)
        )
        assert team.team_points == 0

        json_data = spoof_kc.kc_spoof_json(
            "Danbis",
            "Vardorvis"
        )
        result = dink.parse_kill_count(
            json_data,
            None
        )
        assert result is True

        if i < 9:
            partial_danbis = db_entities.PartialCompletion(
                database.get_partial_completions_by_player_id(
                    player_danbis.player_id
                )[0]
            )
            assert round(
                float(partial_danbis.partial_completion),
                2
            ) == round((i + 1) / 10, 2)
        else:
            assert (
                database.get_partial_completions_by_player_id(
                    player_danbis.player_id
                )
                == []
            )

    team = db_entities.Team(
        database.get_team_by_id(1)
    )
    assert team.team_points == 1

    player_danbis = db_entities.Player(
        database.get_player_by_id(
            player_danbis.player_id
        )
    )
    assert round(player_danbis.tiles_completed, 2) == 1

    # Further kills are still accepted but cannot score
    # or begin progress towards another completion.
    for _ in range(10):
        json_data = spoof_kc.kc_spoof_json(
            "Danbis",
            "Vardorvis"
        )
        result = dink.parse_kill_count(
            json_data,
            None
        )
        assert result is True

        assert (
            database.get_partial_completions_by_player_id(
                player_danbis.player_id
            )
            == []
        )

        team = db_entities.Team(
            database.get_team_by_id(1)
        )
        assert team.team_points == 1

    player_danbis = db_entities.Player(
        database.get_player_by_id(
            player_danbis.player_id
        )
    )
    assert round(player_danbis.tiles_completed, 2) == 1

    completed_tiles = (
        database.get_completed_tiles_by_team_id_and_tile_id(
            1,
            4
        )
    )
    assert len(completed_tiles) == 1


def test_multiple_completions_multiple_players(client):
    database.reset_tables()
    database.read_teams('test_csvs/default_team_1.csv')
    database.read_tiles('test_csvs/default_tiles_3.csv')

    player_deidera = db_entities.Player(
        database.get_player_by_name("Deidera")
    )
    player_danbis = db_entities.Player(
        database.get_player_by_name("Danbis")
    )

    # Danbis contributes 6 of the 10 kills required.
    for i in range(6):
        team = db_entities.Team(
            database.get_team_by_id(1)
        )
        assert team.team_points == 0

        json_data = spoof_kc.kc_spoof_json(
            "Danbis",
            "Vardorvis"
        )
        result = dink.parse_kill_count(
            json_data,
            None
        )
        assert result is True

        partial_danbis = db_entities.PartialCompletion(
            database.get_partial_completions_by_player_id(
                player_danbis.player_id
            )[0]
        )
        assert round(
            float(partial_danbis.partial_completion),
            2
        ) == round((i + 1) / 10, 2)

    # Deidera contributes the remaining 4 kills.
    for i in range(4):
        team = db_entities.Team(
            database.get_team_by_id(1)
        )
        assert team.team_points == 0

        json_data = spoof_kc.kc_spoof_json(
            "Deidera",
            "Vardorvis"
        )
        result = dink.parse_kill_count(
            json_data,
            None
        )
        assert result is True

        if i < 3:
            partial_deidera = db_entities.PartialCompletion(
                database.get_partial_completions_by_player_id(
                    player_deidera.player_id
                )[0]
            )
            assert round(
                float(partial_deidera.partial_completion),
                2
            ) == round((i + 1) / 10, 2)
        else:
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

    player_deidera = db_entities.Player(
        database.get_player_by_name("Deidera")
    )
    player_danbis = db_entities.Player(
        database.get_player_by_name("Danbis")
    )

    assert round(player_danbis.tiles_completed, 2) == 0.6
    assert round(player_deidera.tiles_completed, 2) == 0.4

    # Further kills from either player are accepted as KC events,
    # but cannot start a second completion of the same tile.
    for _ in range(4):
        json_data = spoof_kc.kc_spoof_json(
            "Deidera",
            "Vardorvis"
        )
        result = dink.parse_kill_count(
            json_data,
            None
        )
        assert result is True

    for _ in range(6):
        json_data = spoof_kc.kc_spoof_json(
            "Danbis",
            "Vardorvis"
        )
        result = dink.parse_kill_count(
            json_data,
            None
        )
        assert result is True

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

    player_deidera = db_entities.Player(
        database.get_player_by_name("Deidera")
    )
    player_danbis = db_entities.Player(
        database.get_player_by_name("Danbis")
    )

    assert round(player_danbis.tiles_completed, 2) == 0.6
    assert round(player_deidera.tiles_completed, 2) == 0.4

    completed_tiles = (
        database.get_completed_tiles_by_team_id_and_tile_id(
            1,
            4
        )
    )
    assert len(completed_tiles) == 1


def test_single_player_overcompletion(client):
    database.reset_tables()
    database.read_teams('test_csvs/default_team_1.csv')
    database.read_tiles('test_csvs/default_tiles_3.csv')

    player_danbis = db_entities.Player(
        database.get_player_by_name("Danbis")
    )

    for i in range(1, 30):
        json_data = spoof_kc.kc_spoof_json(
            "Danbis",
            "Vardorvis"
        )
        result = dink.parse_kill_count(
            json_data,
            None
        )
        assert result is True

        if i < 10:
            partial_danbis = db_entities.PartialCompletion(
                database.get_partial_completions_by_player_id(
                    player_danbis.player_id
                )[0]
            )
            assert round(
                float(partial_danbis.partial_completion),
                2
            ) == round(i / 10, 2)

        else:
            assert (
                database.get_partial_completions_by_player_id(
                    player_danbis.player_id
                )
                == []
            )

            player_danbis = db_entities.Player(
                database.get_player_by_name("Danbis")
            )
            assert player_danbis.tiles_completed == 1

            team = db_entities.Team(
                database.get_team_by_id(1)
            )
            assert team.team_points == 1

    completed_tiles = (
        database.get_completed_tiles_by_team_id_and_tile_id(
            1,
            4
        )
    )
    assert len(completed_tiles) == 1

    player_danbis = db_entities.Player(
        database.get_player_by_name("Danbis")
    )
    assert player_danbis.tiles_completed == 1

    team = db_entities.Team(
        database.get_team_by_id(1)
    )
    assert team.team_points == 1


def test_multiplayer_overcompletion(client):
    database.reset_tables()
    database.read_teams('test_csvs/default_team_1.csv')
    database.read_tiles('test_csvs/default_tiles_3.csv')

    player_danbis = db_entities.Player(
        database.get_player_by_name("Danbis")
    )

    # Danbis completes the tile with his first 10 kills.
    for i in range(1, 16):
        json_data = spoof_kc.kc_spoof_json(
            "Danbis",
            "Vardorvis"
        )
        result = dink.parse_kill_count(
            json_data,
            None
        )
        assert result is True

        if i < 10:
            partial_danbis = db_entities.PartialCompletion(
                database.get_partial_completions_by_player_id(
                    player_danbis.player_id
                )[0]
            )
            assert round(
                float(partial_danbis.partial_completion),
                2
            ) == round(i / 10, 2)

        else:
            assert (
                database.get_partial_completions_by_player_id(
                    player_danbis.player_id
                )
                == []
            )

    team = db_entities.Team(
        database.get_team_by_id(1)
    )
    assert team.team_points == 1

    player_danbis = db_entities.Player(
        database.get_player_by_name("Danbis")
    )
    assert round(player_danbis.tiles_completed, 2) == 1

    # Another player's later kills are accepted as KC events,
    # but cannot contribute to an already-completed tile.
    player_deidera = db_entities.Player(
        database.get_player_by_name("Deidera")
    )

    for _ in range(14):
        json_data = spoof_kc.kc_spoof_json(
            "Deidera",
            "Vardorvis"
        )
        result = dink.parse_kill_count(
            json_data,
            None
        )
        assert result is True

        assert (
            database.get_partial_completions_by_player_id(
                player_deidera.player_id
            )
            == []
        )

    assert (
        database.get_partial_completions_by_player_id(
            player_danbis.player_id
        )
        == []
    )

    team = db_entities.Team(
        database.get_team_by_id(1)
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

    completed_tiles = (
        database.get_completed_tiles_by_team_id_and_tile_id(
            1,
            4
        )
    )
    assert len(completed_tiles) == 1