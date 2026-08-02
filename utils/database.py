import os
import csv
import psycopg2
from flask_bcrypt import Bcrypt
from flask_login import UserMixin, logout_user
import utils.db_entities as db_entities
from routes import dink
from utils.db_entities import Player, Tile
from utils.spoofed_jsons import spoof_drop

bcrypt = Bcrypt()

def connect():
    return psycopg2.connect(
        dbname=os.getenv('PGDATABASE'),
        user=os.getenv('PGUSER'),
        password=os.getenv('PGPASSWORD'),
        host=os.getenv('PGHOST'),
        port=os.getenv('PGPORT')
    )

def ensure_schema():
    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute('''
            ALTER TABLE players
            ADD COLUMN IF NOT EXISTS discord_user_id BIGINT
        ''')

        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_players_discord_user_id
            ON players (discord_user_id)
            WHERE discord_user_id IS NOT NULL
        ''')

        cursor.execute('''
            ALTER TABLE teams
            ADD COLUMN IF NOT EXISTS discord_role_id BIGINT
        ''')

        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_teams_discord_role_id
            ON teams (discord_role_id)
            WHERE discord_role_id IS NOT NULL
        ''')

# User authentication functions

class User(UserMixin):
    def __init__(self, user_id, username, email, password, is_admin=False):
        self.id = user_id
        self.username = username
        self.email = email
        self.password = password
        self.is_admin = is_admin

def add_user(username, email, password):
    with connect() as conn:
        cursor = conn.cursor()
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        cursor.execute(
            "INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
            (username, email, hashed_password)
        )
        conn.commit()


def get_tile_names():
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT tile_name FROM tiles")
        tiles = cursor.fetchall()

    # Extract the tile names from the fetched records
    tile_names = [tile[0] for tile in tiles]
    return tile_names


def get_player_names():
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT player_name FROM players")
        players = cursor.fetchall()

    # Extract the player names from the fetched records
    player_names = [player[0] for player in players]
    return player_names


def update_tile(tile_id,new_tile_id, tile_name, tile_type, old_tile_triggers, tile_triggers, tile_trigger_weights, tile_unique_drops, tile_triggers_required, tile_repetition, tile_points, tile_rules):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE tiles
            SET tile_id = %s, tile_name = %s, tile_type = %s, tile_triggers = %s, tile_trigger_weights = %s, tile_unique_drops = %s,
                tile_triggers_required = %s, tile_repetition = %s, tile_points = %s, tile_rules = %s
            WHERE tile_id = %s
        ''', (new_tile_id, tile_name, tile_type, tile_triggers, tile_trigger_weights, tile_unique_drops, tile_triggers_required,
              tile_repetition, tile_points, tile_rules, tile_id))

        cursor.execute('''
            DELETE FROM drop_whitelist
            WHERE tile_id = %s
        ''', (tile_id,))

        conn.commit()

    old_trigger_set = set()
    for x in old_tile_triggers.split(','):
        for trigger in x.split('/'):
            old_trigger_set.add(trigger)

    new_trigger_set = set()
    for x in tile_triggers.split(','):
        for trigger in x.split('/'):
            add_drop_whitelist(trigger, tile_id)
            new_trigger_set.add(trigger)

    for trigger in new_trigger_set:
        if trigger not in old_trigger_set:
            drops = get_drops_by_item_name(trigger.strip())
            for drop in drops:
                drop = db_entities.Drop(drop)
                remove_drop_by_pk(drop.drop_pk)
                json_data = spoof_drop.award_drop_json(drop.player_name, drop.drop_name, drop.drop_value, drop.drop_quantity)
                result = dink.parse_loot(json_data, None)


def remove_drop_by_pk(drop_pk):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM drops WHERE drop_pk = %s", (drop_pk))

def remove_tile(tile_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            DELETE FROM drop_whitelist
            WHERE tile_id = %s
        ''', (tile_id,))
        cursor.execute("DELETE FROM tiles WHERE tile_id = %s", (tile_id,))
        conn.commit()


def get_user_by_email(email):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        result = cursor.fetchone()
        if result:
            return User(result[0], result[1], result[2], result[3])
        return None

def get_user_by_id(user_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        result = cursor.fetchone()
        try:
            if result:
                return User(result[0], result[1], result[2], result[3], result[4])
            return None
        except:
            return None

def check_password(hashed_password, password):
    return bcrypt.check_password_hash(hashed_password, password)

# Add these functions to your existing database functions

# Functions for 'teams' table
def add_team_points(team_id, team_points):
    with connect() as conn:
        cursor = conn.cursor()
        update_query = '''
            UPDATE teams
            SET team_points = team_points + %s
            WHERE team_id = %s
        '''
        cursor.execute(update_query, (team_points, team_id,))
        conn.commit()

def rename_team(old_team_name, new_team_name):
    with connect() as conn:
        cursor = conn.cursor()
        update_query = '''
            UPDATE teams
            SET team_name = %s
            WHERE lower(team_name) = lower(%s)
            '''
        cursor.execute(update_query, (new_team_name, old_team_name,))

# Functions for 'teams' table
def add_team(team_name, team_points, team_webhook):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO teams (team_name, team_points, team_webhook) VALUES (%s, %s, %s)",
                       (team_name, team_points, team_webhook))
        return cursor.execute("SELECT team_id from teams where lower(team_name) = lower(%s)", (team_name,))


def remove_team(team_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM teams WHERE team_id = %s", (team_id,))


def get_teams():
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM teams")
        return cursor.fetchall()


def get_team_by_id(team_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM teams where team_id = %s", (team_id,))
        return cursor.fetchone()


def get_team_by_name(team_name):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM teams where lower(team_name) = lower(%s)", (team_name,))
        return cursor.fetchone()

def get_team_by_discord_role_id(discord_role_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM teams WHERE discord_role_id = %s",
            (discord_role_id,)
        )
        return cursor.fetchone()

def set_team_discord_role_id(team_id, discord_role_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE teams
            SET discord_role_id = %s
            WHERE team_id = %s
            """,
            (discord_role_id, team_id)
        )


# Functions for 'players' table
def add_player(player_name, deaths, gp_gained, tiles_completed, team_id, pet_count):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO players (player_name, deaths, gp_gained, tiles_completed, team_id, pet_count) VALUES (%s, %s, %s, %s, %s, %s)",
            (player_name, deaths, gp_gained, tiles_completed, team_id, pet_count))


def add_death_by_playername(rsn):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE players SET deaths = deaths + 1 WHERE lower(player_name) = lower(%s)", (rsn,))


def add_pet_by_playername(rsn):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE players SET pet_count = pet_count + 1 WHERE lower(player_name) = lower(%s)", (rsn,))

def get_total_pets_by_team(team_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM players WHERE team_id = %s", (team_id,))
    total_pets = 0
    for player in cursor.fetchall():
        player_obj = db_entities.Player(player)
        total_pets = total_pets + player_obj.pet_count
    return total_pets

def add_player_tile_completions(player_id, tiles_completed):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE players
            SET tiles_completed = tiles_completed + %s
            WHERE player_id = %s
        ''', (tiles_completed, player_id))


def rename_player(old_player_name, new_player_name):
    with connect() as conn:
        cursor = conn.cursor()
        update_query = '''
            UPDATE players
            SET player_name = %s
            WHERE lower(player_name) = lower(%s)
            '''
        cursor.execute(update_query, (new_player_name, old_player_name,))




def remove_player(player_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM players WHERE player_id = %s", (player_id,))


def get_players():
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM players")
        return cursor.fetchall()


def get_players_by_team():
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT t.team_name, p.player_id, p.player_name, p.deaths, p.gp_gained, p.tiles_completed, p.pet_count
            FROM players p
            JOIN teams t ON p.team_id = t.team_id
            ORDER BY t.team_name, p.player_id
        ''')
        players = cursor.fetchall()

    # Group players by team name
    players_by_team = {}
    for player in players:
        team_name = player[0]
        if team_name not in players_by_team:
            players_by_team[team_name] = []
        players_by_team[team_name].append(player[1:])

    return players_by_team


def get_players_by_team_id(team_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM players WHERE team_id = %s", (team_id,))
        return cursor.fetchall()


def get_player_by_name(player_name):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM players where lower(player_name) = lower(%s)", (player_name,))
        return cursor.fetchone()


def get_player_by_id(player_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM players where player_id = %s", (player_id,))
        return cursor.fetchone()

def get_player_by_discord_user_id(discord_user_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM players WHERE discord_user_id = %s",
            (discord_user_id,)
        )
        return cursor.fetchone()

def link_player_to_discord(player_id, discord_user_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE players
            SET discord_user_id = %s
            WHERE player_id = %s
            """,
            (discord_user_id, player_id)
        )

# Functions for 'drops' table
def add_drop(team_id, player_id, player_name, drop_name, drop_value, drop_quantity, drop_source):
    with connect() as conn:
        cursor = conn.cursor()

        # Insert the new drop and return the primary key
        cursor.execute('''
            INSERT INTO drops (team_id, player_id, player_name, drop_name, drop_value, drop_quantity, drop_source) 
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING drops_pk
        ''', (team_id, player_id, player_name, drop_name, drop_value, drop_quantity, drop_source))

        # Fetch the newly created primary key
        drop_pk = cursor.fetchone()[0]

        # Update the player's gp_gained based on the drop
        cursor.execute('''
            UPDATE Players 
            SET gp_gained = gp_gained + %s 
            WHERE player_id = %s
        ''', (drop_value * drop_quantity, player_id))

        # Commit the transaction
        conn.commit()

        # Return the primary key of the new drop
        return drop_pk


def remove_drop_by_pk(drop_pk):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM drops WHERE drops_pk = %s", (drop_pk,))

def remove_drop(player_id, drop_name):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM drops WHERE player_id = %s AND lower(drop_name) = lower(%s)", (player_id, drop_name))


def get_drops():
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM drops")
        return cursor.fetchall()


def get_drops_by_team_id(team_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM drops WHERE team_id = %s", (team_id,))
        return cursor.fetchall()


def get_drops_by_player_id(player_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM drops WHERE player_id = %s", (player_id,))
        return cursor.fetchall()


# Functions for 'killcount' table
def add_killcount(player_id, team_id, boss_name, kills):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO killcount (player_id, team_id, boss_name, kills) VALUES (%s, %s, %s, %s)",
                       (player_id, team_id, boss_name, kills))


def remove_killcount(player_id, boss_name):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM killcount WHERE player_id = %s AND lower(boss_name) = lower(%s)", (player_id, boss_name))


def get_killcounts():
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM killcount")
        return cursor.fetchall()


# Functions for 'drop_whitelist' table
def add_drop_whitelist(drop_name, tile_id):
    with connect() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO drop_whitelist (drop_name, tile_id) VALUES (%s, %s)",
                           (drop_name, tile_id,))
        except:
            print("Warning! Duplicate trigger found! " + drop_name)

def update_drop_whitelist_name(old_name, new_name):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE drop_whitelist SET drop_name = %s WHERE drop_name = %s",
                     (new_name, old_name,))


def remove_drop_whitelist(drop_name):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM drop_whitelist WHERE lower(drop_name) = lower(%s)", (drop_name,))

def remove_drop_whitelist_by_tile_id(tile_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM drop_whitelist WHERE tile_id = %s", (tile_id,))

def get_drop_whitelist():
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM drop_whitelist")
        return cursor.fetchall()


def get_drop_whitelist_by_item_name(item_name):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM drop_whitelist WHERE lower(drop_name) = lower(%s)", (item_name,))
        return cursor.fetchone()


# Functions for 'completed_tiles' table
def add_completed_tile(tile_id, team_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO completed_tiles (tile_id, team_id) VALUES (%s, %s)",
                       (tile_id, team_id))



def remove_completed_tile(tile_id, team_id):
    with connect() as conn:
        cursor = conn.cursor()
        completed_tile = db_entities.CompletedTile(
            cursor.execute("SELECT * FROM completed_tiles WHERE lower(tile_name) = lower(%s) and team_id = %s",
                           (tile_id, team_id)).fetchone())
        cursor.execute("DELETE FROM completed_tiles WHERE completed_tile_pk = %s", (completed_tile.completed_tile_pk))


def get_completed_tiles():
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM completed_tiles")
        return cursor.fetchall()

def get_completed_tiles_by_team_id(team_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM completed_tiles where team_id = %s", (team_id,))
        return cursor.fetchall()

def get_completed_tiles_by_team_id_and_tile_id(team_id, tile_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM completed_tiles where team_id = %s and tile_id = %s", (team_id, tile_id))
        return cursor.fetchall()


def add_tile(tile_name, tile_type, tile_triggers, tile_trigger_weights, tile_unique_drops, tile_triggers_required,
             tile_repetition, tile_points, tile_rules):
    with connect() as conn:
        cursor = conn.cursor()

        # Start at 1 and increment upwards until we find an unused tile_id
        available_id = 1
        while True:
            cursor.execute("SELECT 1 FROM tiles WHERE tile_id = %s", (available_id,))
            if not cursor.fetchone():
                break
            available_id += 1

        if tile_unique_drops == "N/A" or tile_unique_drops == "":
            tile_unique_drops = "FALSE"
        if tile_triggers_required == "N/A" or tile_triggers_required == "":
            tile_triggers_required = 0

        cursor.execute(
            "INSERT INTO tiles (tile_id, tile_name, tile_type, tile_triggers, tile_trigger_weights, tile_unique_drops, tile_triggers_required, tile_repetition, tile_points, tile_rules) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (available_id, tile_name, tile_type, tile_triggers, tile_trigger_weights, tile_unique_drops,
             tile_triggers_required, tile_repetition, tile_points, tile_rules))
        conn.commit()
    for x in tile_triggers.split(','):
        for trigger in x.split('/'):
            add_drop_whitelist(trigger.strip(), available_id)



def update_tile_trigger(tile_id, tile_trigger):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE tiles SET tile_triggers = %s WHERE tile_id = %s", (tile_trigger, tile_id))

# ... Repeat similar functions for 'drops', 'killcount', 'drop_whitelist', and 'completed_tiles' tables ...

def get_tiles():
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tiles ORDER BY tile_id")
        return cursor.fetchall()


def get_niche_tiles():
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tiles WHERE tile_type = %s", ("NICHE",))
        return cursor.fetchall()


def get_tile_by_drop(drop_name):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM drop_whitelist where lower(drop_name) = lower(%s)", (drop_name,))
        try:
            tile_id = cursor.fetchone()[1]
        except:
            return None
        cursor.execute("SELECT * FROM tiles where tile_id = %s", (tile_id,))
        return cursor.fetchone()

def get_tile_by_id(tile_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tiles where tile_id = %s", (tile_id,))
        return cursor.fetchone()

def get_tile_by_name(tile_name):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tiles where lower(tile_name) = lower(%s)", (tile_name,))
        return cursor.fetchone()

def get_tile_by_type(tile_type):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tiles where tile_type = %s", (tile_type,))
        return cursor.fetchall()

def get_drops_by_item_name_and_team_id(item_name, team_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM drops where team_id = %s and lower(drop_name) = lower(%s)", (team_id, item_name,))
        return cursor.fetchall()

def update_player(player_id, player_name, deaths, gp_gained, tiles_completed, team_id, pet_count):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE players
            SET player_name = %s, deaths = %s, gp_gained = %s, tiles_completed = %s, team_id = %s, pet_count = %s
            WHERE player_id = %s
        ''', (player_name, deaths, gp_gained, tiles_completed, team_id, pet_count, player_id))
        conn.commit()


def update_team_webhook(team_id, team_webhook):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE teams set team_webhook = %s where team_id = %s", (team_webhook, team_id,))
        conn.commit()

def get_drops_by_item_name(item_name):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM drops WHERE lower(drop_name) = lower(%s)", (item_name,))
        return cursor.fetchall()
# Functions for 'killcount' table
def add_killcount(player_id, team_id, bossname, kills):
    with connect() as conn:
        cursor = conn.cursor()

        # Check if the row already exists
        cursor.execute("SELECT * FROM KillCount WHERE player_id = %s AND team_id = %s AND lower(boss_name) = lower(%s)",
                       (player_id, team_id, bossname))
        row = cursor.fetchone()

        if row is not None:
            # If the row exists, update the kills
            cursor.execute(
                "UPDATE KillCount SET kills = kills + %s WHERE player_id = %s AND team_id = %s AND lower(boss_name) = lower(%s)",
                (kills, player_id, team_id, bossname))
        else:
            # If the row doesn't exist, insert a new row
            cursor.execute("INSERT INTO KillCount (player_id, team_id, boss_name, kills) VALUES (%s, %s, %s, %s)",
                           (player_id, team_id, bossname, kills))

        # Commit the changes
        conn.commit()

def get_partial_completions():
    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM partial_completions")
        return cursor.fetchall()

def add_player_partial_completions(player_id, team_id, tile_id, value):
    with connect() as conn:
        cursor = conn.cursor()

        # Check if the row already exists
        cursor.execute("SELECT * FROM partial_completions WHERE player_id = %s AND team_id = %s AND tile_id = %s",
                       (player_id, team_id, tile_id))
        row = cursor.fetchone()

        if row is not None:
            # If the row exists, update the kills
            cursor.execute(
                "UPDATE partial_completions SET partial_completion = partial_completion + %s WHERE player_id = %s AND team_id = %s AND tile_id = %s",
                (value, player_id, team_id, tile_id))
        else:
            cursor.execute("INSERT INTO partial_completions (player_id, team_id, tile_id, partial_completion) VALUES (%s, %s, %s, %s)",
                           (player_id, team_id, tile_id, value))

        conn.commit()

def get_partial_completions_by_team_id_and_tile_id(team_id, tile_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM partial_completions WHERE team_id = %s AND tile_id = %s", (team_id, tile_id))
        return cursor.fetchall()

def get_partial_completions_by_team_id(team_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM partial_completions WHERE team_id = %s", (team_id,))
        return cursor.fetchall()

def get_partial_completions_by_player_id(player_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM partial_completions WHERE player_id = %s", (player_id,))
        return cursor.fetchall()

def remove_partial_completion(partial_completion_pk):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM partial_completions WHERE partial_completion_pk = %s", (partial_completion_pk,))

def get_killcount_by_team_id_and_boss_name(team_id, boss_name):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM killcount WHERE team_id = %s AND lower(boss_name) = lower(%s)", (team_id, boss_name))
        return cursor.fetchall()


def get_killcount_by_team_id(team_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM killcount WHERE team_id = %s", (team_id,))
        return cursor.fetchall()


def get_killcount_by_player_id(player_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM killcount WHERE player_id = %s", (player_id,))
        return cursor.fetchall()


def add_manual_progress(tile_name, player_name, progress):
    with connect() as conn:
        cursor = conn.cursor()

        # Find the player
        cursor.execute("SELECT * FROM players WHERE lower(player_name) = lower(%s)", (player_name,))
        player = db_entities.Player(cursor.fetchone())

        # Find the team
        cursor.execute("SELECT * FROM teams where team_id = %s", (player.team_id,))
        team = db_entities.Team(cursor.fetchone())

        # Find the tile
        cursor.execute("SELECT * FROM tiles WHERE lower(tile_name) = lower(%s)", (tile_name,))
        tile = db_entities.Tile(cursor.fetchone())

        # Check if the row already exists
        cursor.execute("SELECT * FROM manual_tile_progress WHERE team_id = %s AND tile_id = %s AND player_id = %s",
                       (team.team_id, tile.tile_id, player.player_id))
        row = cursor.fetchone()

        if row is not None:
            # If the row exists, update the kills
            cursor.execute(
                "UPDATE manual_tile_progress SET progress = progress + %s WHERE team_id = %s AND tile_id = %s AND player_id = %s",
                (progress, team.team_id, tile.tile_id, player.player_id))
        else:
            # If the row doesn't exist, insert a new row
            cursor.execute("INSERT INTO manual_tile_progress (tile_id, team_id, progress, player_id) VALUES (%s, %s, %s, %s)",
                           (tile.tile_id, team.team_id, progress, player.player_id))


def get_manual_progress_by_tile_name_and_team_name(tile_name, team_name):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM teams where lower(team_name) = lower(%s)", (team_name,))
        team = db_entities.Team(cursor.fetchone())

        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tiles where lower(tile_name) = lower(%s)", (tile_name,))
        tile = db_entities.Tile(cursor.fetchone())

        cursor = conn.cursor()
        cursor.execute("SELECT * FROM manual_tile_progress WHERE team_id = %s AND tile_id = %s",
                       (team.team_id, tile.tile_id,))

        progress = 0
        for x in cursor.fetchall():
            progress += x[3]

        return progress


def get_manual_progress_by_tile_id_and_team_id(tile_id, team_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM manual_tile_progress WHERE team_id = %s and tile_id = %s", (team_id, tile_id,))
        try:
            progress = 0
            for item in cursor.fetchall():
                progress = progress + item[3]
            return progress
        except:
            return 0


def add_request(team_name, player_name, tile_name, item_description, image):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO requests (team_name, player_name, tile_name, item_name, evidence) VALUES (%s, %s, %s, %s, %s)", (team_name, player_name, tile_name, item_description, image,))


def get_request():
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM requests")
        return cursor.fetchone()


def delete_request(request_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM requests WHERE request_id = %s", (request_id,))


def add_chats(player_id, team_id, tile_id, chat):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO chats (player_id, team_id, tile_id, chat) VALUES (%s, %s, %s, %s)", (player_id, team_id, tile_id, chat))


def get_chats(chats_pk):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM chats WHERE chats_pk = %s", (chats_pk,))
        return cursor.fetchall()


def get_chats_by_player_id_and_tile_id(player_id, tile_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM chats WHERE player_id = %s and tile_id = %s", (player_id, tile_id))
        return cursor.fetchall()


def get_chats_by_team_id_and_tile_id(team_id, tile_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM chats WHERE team_id = %s and tile_id = %s", (team_id, tile_id))
        return cursor.fetchall()


def delete_chat(chats_pk):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chats WHERE chats_pk = %s", (chats_pk,))

def add_relevant_drop(team_id, player_id, tile_id, tile_name, drop_name, player_name, drops_pk):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO relevant_drops (team_id, player_id, tile_id, tile_name, drop_name, player_name, drops_pk)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (team_id, player_id, tile_id, tile_name, drop_name, player_name, drops_pk))
        conn.commit()

def get_relevant_drop_by_player_id(player_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM relevant_drops WHERE player_id = %s", (player_id,))
        return cursor.fetchall()

def get_relevant_drop_by_team_id(team_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM relevant_drops WHERE team_id = %s", (team_id,))
        return cursor.fetchall()

def get_relevant_drop_by_team_id_and_tile_id(team_id, tile_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM relevant_drops WHERE team_id = %s AND tile_id = %s", (team_id, tile_id,))
        return cursor.fetchall()

def delete_relevant_drop(relevant_drops_pk):
    with connect() as conn:
        cursor = conn.cursor()

        # Fetch the relevant drop details: player_name, tile_id, drop_name
        cursor.execute('''
            SELECT player_name, tile_id, drop_name 
            FROM relevant_drops 
            WHERE relevant_drops_pk = %s
        ''', (relevant_drops_pk,))
        relevant_drop = cursor.fetchone()

        if not relevant_drop:
            raise ValueError(f"Relevant drop with ID {relevant_drops_pk} does not exist.")

        player_name = relevant_drop[0]
        tile_id = relevant_drop[1]
        drop_name = relevant_drop[2]

        # Fetch the trigger values and weights for the relevant tile
        cursor.execute('''
            SELECT tile_triggers, tile_trigger_weights, tile_triggers_required
            FROM tiles 
            WHERE tile_id = %s
        ''', (tile_id,))
        tile_data = cursor.fetchone()

        if not tile_data:
            raise ValueError(f"Tile with ID {tile_id} does not exist.")

        tile_triggers = tile_data[0].split(',')
        tile_trigger_weights = list(map(float, tile_data[1].split(',')))
        tile_triggers_required = tile_data[2]

        # Ensure the drop name exists in the tile triggers
        if drop_name not in tile_triggers:
            raise ValueError(f"Drop '{drop_name}' is not a valid trigger for tile ID {tile_id}.")

        # Calculate the reduction amount using the drop trigger weight
        drop_index = tile_triggers.index(drop_name)
        drop_weight = tile_trigger_weights[drop_index]
        reduction_amount = drop_weight / tile_triggers_required

        # Update the player's partial completion, reducing by the calculated amount
        cursor.execute('''
            UPDATE partial_completions 
            SET partial_completion = partial_completion - %s 
            WHERE player_id = (
                SELECT player_id FROM players WHERE lower(player_name) = lower(%s)
            ) AND tile_id = %s
        ''', (reduction_amount, player_name, tile_id))

        # Delete the relevant drop
        cursor.execute("DELETE FROM relevant_drops WHERE relevant_drops_pk = %s", (relevant_drops_pk,))

        # Delete the associated drop in the drops table
        cursor.execute("DELETE FROM drops WHERE drops_pk = (SELECT drops_pk FROM relevant_drops WHERE relevant_drops_pk = %s)", (relevant_drops_pk,))

        # Commit



def change_player_team(player_id, new_team_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE chats SET team_id = %s WHERE player_id = %s", (new_team_id, player_id,))
        cursor.execute("UPDATE drops SET team_id = %s WHERE player_id = %s", (new_team_id, player_id,))
        cursor.execute("UPDATE killcount SET team_id = %s WHERE player_id = %s", (new_team_id, player_id,))
        cursor.execute("UPDATE partial_completions SET team_id = %s WHERE player_id = %s", (new_team_id, player_id,))
        cursor.execute("UPDATE relevant_drops SET team_id = %s WHERE player_id = %s", (new_team_id, player_id,))
        cursor.execute("UPDATE players SET team_id = %s WHERE player_id = %s", (new_team_id, player_id,))
        cursor.execute("UPDATE manual_tile_progress SET team_id = %s WHERE player_id = %s", (new_team_id, player_id,))
        conn.commit()


def reset_tables():
    # Drop all tables
    print("connecting to db")
    conn = connect()
    print("connected")
    cursor = conn.cursor()
    # Get the list of all tables
    cursor.execute(
        "SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname != 'pg_catalog' AND schemaname != 'information_schema';")
    tables = cursor.fetchall()

    # Drop each table
    for table in tables:
        cursor.execute(f"DROP TABLE IF EXISTS {table[0]} CASCADE;")

    print("All tables dropped successfully.")
    print("Recreating now...")
    cursor.execute('''
        CREATE TABLE users (
            user_id SERIAL PRIMARY KEY,
            username text NOT NULL,
            email text UNIQUE NOT NULL,
            password text NOT NULL,
            is_admin boolean NOT NULL DEFAULT FALSE
        )
        ''')

    # Create the 'drops' table

    cursor.execute('''
            CREATE TABLE teams (
                team_name text,
                team_points real,
                team_webhook text,
                team_id SERIAL PRIMARY KEY,
                discord_role_id BIGINT
            )
            ''')

    cursor.execute('''
            CREATE UNIQUE INDEX idx_teams_discord_role_id
            ON teams (discord_role_id)
            WHERE discord_role_id IS NOT NULL
        ''')

    cursor.execute('''
            CREATE TABLE players (
                player_id SERIAL PRIMARY KEY,
                player_name text,
                deaths integer,
                gp_gained integer,
                tiles_completed real,
                team_id integer,
                pet_count integer,
                discord_user_id BIGINT,
                FOREIGN KEY(team_id) REFERENCES teams(team_id) ON DELETE CASCADE
            )
            ''')

    cursor.execute('''
            CREATE UNIQUE INDEX idx_players_discord_user_id
            ON players (discord_user_id)
            WHERE discord_user_id IS NOT NULL
            ''')

    cursor.execute('''
            CREATE TABLE drops (
                team_id integer,
                player_id integer,
                player_name text,
                drop_name text,
                drop_value real,
                drop_quantity integer,
                drop_source text,
                drops_pk SERIAL PRIMARY KEY,
                FOREIGN KEY(player_id) REFERENCES players(player_id) ON DELETE CASCADE,
                FOREIGN KEY(team_id) REFERENCES teams(team_id) ON DELETE CASCADE
            )
        ''')

    cursor.execute('''
            CREATE TABLE killcount (
                player_id integer,
                team_id integer,
                boss_name text,
                kills integer,
                killcount_pk SERIAL PRIMARY KEY,
                FOREIGN KEY(player_id) REFERENCES players(player_id) ON DELETE CASCADE,
                FOREIGN KEY (team_id) REFERENCES teams(team_id) ON DELETE CASCADE
            )''')

    cursor.execute('''
            CREATE TABLE tiles (
                tile_id SERIAL PRIMARY KEY,
                tile_name text,
                tile_type text,
                tile_triggers text,
                tile_trigger_weights text,
                tile_unique_drops boolean,
                tile_triggers_required int,
                tile_repetition int,
                tile_points real,
                tile_rules text
            )
            ''')

    cursor.execute('''
            CREATE TABLE drop_whitelist (
                drop_name text PRIMARY KEY,
                tile_id int,
                FOREIGN KEY (tile_id) REFERENCES tiles(tile_id) ON DELETE CASCADE
            )''')

    cursor.execute('''
            CREATE TABLE completed_tiles (
                team_id integer,
                tile_id integer,
                completed_tile_pk SERIAL PRIMARY KEY,
                FOREIGN KEY (tile_id) REFERENCES tiles(tile_id) ON DELETE CASCADE,
                FOREIGN KEY (team_id) REFERENCES teams(team_id) ON DELETE CASCADE
            )
            ''')

    cursor.execute('''
            CREATE TABLE manual_tile_progress (
                player_id integer,
                team_id integer,
                tile_id integer,
                progress real,
                manual_tile_progress_pk SERIAL PRIMARY KEY,
                FOREIGN KEY (team_id) REFERENCES teams(team_id) ON DELETE CASCADE,
                FOREIGN KEY (tile_id) REFERENCES tiles(tile_id) ON DELETE CASCADE,
                FOREIGN KEY (player_id) REFERENCES players(player_id) ON DELETE CASCADE
            )
            ''')

    cursor.execute('''
            CREATE TABLE requests (
                request_id SERIAL PRIMARY KEY,
                team_name text,
                player_name text,
                tile_name text, 
                item_name text,
                evidence text
            )
            ''')

    cursor.execute('''
            CREATE TABLE chats (
                player_id integer,
                team_id integer,
                tile_id integer,
                chat text,
                chats_pk SERIAL PRIMARY KEY,
                FOREIGN KEY(team_id) REFERENCES teams(team_id) ON DELETE CASCADE,
                FOREIGN KEY(player_id) REFERENCES players(player_id) ON DELETE CASCADE,
                FOREIGN KEY(tile_id) REFERENCES tiles(tile_id) ON DELETE CASCADE                
            )
            ''')

    cursor.execute('''
            CREATE TABLE partial_completions (
                team_id integer,
                tile_id integer,
                player_id integer,
                partial_completion real,
                partial_completion_pk SERIAL PRIMARY KEY,
                FOREIGN KEY(team_id) REFERENCES teams(team_id) ON DELETE CASCADE,
                FOREIGN KEY(tile_id) REFERENCES tiles(tile_id) ON DELETE CASCADE,
                FOREIGN KEY(player_id) REFERENCES players(player_id) ON DELETE CASCADE
            )
            ''')

    cursor.execute('''
            CREATE TABLE relevant_drops (
                team_id integer,
                player_id integer,
                tile_id integer,
                tile_name text,
                drop_name text,
                player_name text,
                drops_pk SERIAL,
                relevant_drops_pk SERIAL PRIMARY KEY,
                FOREIGN KEY(drops_pk) REFERENCES  drops(drops_pk) ON DELETE CASCADE,
                FOREIGN KEY(team_id) REFERENCES teams(team_id) ON DELETE CASCADE,
                FOREIGN KEY(tile_id) REFERENCES tiles(tile_id) ON DELETE CASCADE,
                FOREIGN KEY(player_id) REFERENCES players(player_id) ON DELETE CASCADE
            )
            ''')

    # Save (commit) the changes
    conn.commit()
    print("Finished creating!")

    # Close the connection
    conn.close()


def read_tiles(file_name):
    tiles = []
    with open(file_name, 'r') as file:
        reader = csv.reader(file)
        for row in reader:
            tiles.append(row)

    for i in range(1, len(tiles)):
        whitelist_items = []
        tile = tiles[i]
        tile_name = tile[0]
        tile_type = tile[1]
        tile_triggers = tile[2]
        for a in tile_triggers.split('/'):
            for b in a.split(','):
                whitelist_items.append(b)
        tile_trigger_weights = tile[3]
        tile_unique_drops = tile[4]
        tile_triggers_required = tile[5]
        tile_repetition = tile[6]
        tile_points = tile[7]
        tile_rules = tile[8]
        add_tile(tile_name, tile_type, tile_triggers, tile_trigger_weights, tile_unique_drops, tile_triggers_required,
                 tile_repetition, tile_points, tile_rules)
        tile = Tile(get_tile_by_name(tile_name))
        for item in whitelist_items:
            if item.strip() == "":
                continue
            add_drop_whitelist(item.strip(), tile.tile_id)


def read_teams(file_name):
    teams = []
    with open(file_name, 'r') as file:
        reader = csv.reader(file)
        for row in reader:
            teams.append(row)

    for i in range(1, len(teams)):
        team = teams[i]
        team_name = team[0]
        team_webhook = team[1]
        players = team[2:]
        add_team(team_name, 0, team_webhook)
        team_obj = db_entities.Team(get_team_by_name(team_name))
        for player in players:
            player = player.strip()
            if player == "":
                continue
            add_player(player, 0, 0, 0, team_obj.team_id, 0)

    return teams

def get_relevant_drop_by_id(drop_pk):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM relevant_drops WHERE relevant_drops_pk = %s", (drop_pk,))
        return cursor.fetchone()


def update_relevant_drop(relevant_drops_pk, new_tile_name, new_drop_name, new_player_name):
    with connect() as conn:
        cursor = conn.cursor()

        # Fetch tile_id from the new tile_name
        cursor.execute("SELECT tile_id FROM tiles WHERE lower(tile_name) = lower(%s)", (new_tile_name,))
        tile = cursor.fetchone()
        if not tile:
            raise ValueError(f"Tile with name {new_tile_name} does not exist.")
        new_tile_id = tile[0]

        # Get the trigger value and trigger weight for the tile
        cursor.execute('''
            SELECT tile_triggers, tile_trigger_weights, tile_triggers_required
            FROM tiles 
            WHERE tile_id = %s
        ''', (new_tile_id,))
        tile_data = cursor.fetchone()
        tile_triggers = tile_data[0].split(',')  # Each trigger can be a group
        tile_trigger_weights = list(map(float, tile_data[1].split(',')))
        tile_trigger_weight_required = tile_data[2]

        # Parse triggers and associate them with weights
        trigger_to_weight_map = {}
        for i, trigger_group in enumerate(tile_triggers):
            triggers = [t.strip() for t in trigger_group.split('/')]  # Split by '/'
            weight = tile_trigger_weights[i]
            for trigger in triggers:
                trigger_to_weight_map[trigger] = weight

        # Ensure the new drop name exists in the tile triggers
        if new_drop_name not in trigger_to_weight_map:
            raise ValueError(f"Drop '{new_drop_name}' is not a valid trigger for tile '{new_tile_name}'.")

        # Get the trigger weight for this drop
        drop_weight = trigger_to_weight_map[new_drop_name]

        # Fetch the old player associated with this relevant drop and the old tile
        cursor.execute('''
            SELECT player_name, tile_id, player_id 
            FROM relevant_drops 
            WHERE relevant_drops_pk = %s
        ''', (relevant_drops_pk,))
        old_relevant_drop = cursor.fetchone()
        old_player_name = old_relevant_drop[0]
        old_tile_id = old_relevant_drop[1]
        old_player_id = old_relevant_drop[2]

        # Calculate the reduction amount for the old player's partial completion
        reduction_amount = drop_weight / tile_trigger_weight_required

        # Reduce the old player's partial completion for the tile
        cursor.execute('''
            UPDATE partial_completions 
            SET partial_completion = partial_completion - %s 
            WHERE player_id = %s AND tile_id = %s
        ''', (reduction_amount, old_player_id, old_tile_id))

        # Fetch the new player's player_id and team_id
        cursor.execute('''
            SELECT player_id, team_id 
            FROM players 
            WHERE lower(player_name) = lower(%s)
        ''', (new_player_name,))
        new_player = cursor.fetchone()
        if not new_player:
            raise ValueError(f"Player with name {new_player_name} does not exist.")
        new_player_id, new_team_id = new_player

        # Add the completion amount to the new player
        cursor.execute('''
            UPDATE partial_completions 
            SET partial_completion = partial_completion + %s 
            WHERE player_id = %s AND tile_id = %s
        ''', (reduction_amount, new_player_id, new_tile_id))

        # Fetch the drop details (quantity and value) for calculating the gold gained
        cursor.execute('''
            SELECT drop_quantity, drop_value 
            FROM drops 
            WHERE drops_pk = (
                SELECT drops_pk FROM relevant_drops WHERE relevant_drops_pk = %s
            )
        ''', (relevant_drops_pk,))
        drop_data = cursor.fetchone()
        drop_quantity, drop_value = drop_data

        # Calculate the total gold for this drop
        gold_gained = drop_quantity * drop_value

        # Remove the gold gained from the old player
        cursor.execute('''
            UPDATE players 
            SET gp_gained = gp_gained - %s 
            WHERE player_id = %s
        ''', (gold_gained, old_player_id))

        # Add the gold gained to the new player
        cursor.execute('''
            UPDATE players 
            SET gp_gained = gp_gained + %s 
            WHERE player_id = %s
        ''', (gold_gained, new_player_id))

        # Update the relevant drop record with the new details (player_id, team_id, tile_id, tile_name, drop_name, player_name)
        cursor.execute('''
            UPDATE relevant_drops
            SET tile_id = %s, tile_name = %s, drop_name = %s, player_name = %s, player_id = %s, team_id = %s
            WHERE relevant_drops_pk = %s
        ''', (new_tile_id, new_tile_name, new_drop_name, new_player_name, new_player_id, new_team_id, relevant_drops_pk))

        # Also update the drop name, player, and team in the drops table for the relevant player
        cursor.execute('''
            UPDATE drops
            SET drop_name = %s, team_id = %s, player_id = %s
            WHERE drops_pk = (
                SELECT drops_pk FROM relevant_drops WHERE relevant_drops_pk = %s
            )
        ''', (new_drop_name, new_team_id, new_player_id, relevant_drops_pk))

        conn.commit()




def get_tile_triggers():
    """
    Fetches all tiles and their associated triggers from the database and
    returns them as a dictionary where the key is the tile name and the value is a list of triggers.
    """
    with connect() as conn:
        cursor = conn.cursor()

        # Query to fetch tile names and their associated triggers
        cursor.execute("SELECT tile_name, tile_triggers FROM tiles")

        # Fetch all rows from the result
        rows = cursor.fetchall()

        # Create a dictionary mapping tile_name to a list of triggers
        tile_triggers = {}
        for row in rows:
            tile_name = row[0]
            triggers = [trigger.strip() for trigger in row[1].replace('/', ',').split(',') if trigger]  # Split and strip
            tile_triggers[tile_name] = triggers

    return tile_triggers


def get_tile_types():
    """
    Fetches all tiles and their types from the database.
    Returns a dictionary where the key is the tile name and the value is its type.
    """
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT tile_name, tile_type FROM tiles")
        rows = cursor.fetchall()

        tile_types = {}
        for row in rows:
            tile_name = row[0]
            tile_type = row[1]
            tile_types[tile_name] = tile_type

    return tile_types


def get_drop_by_id(drop_pk):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM drops WHERE drops_pk = %s", (drop_pk,))
        return cursor.fetchone()


def update_drop(drop_pk, new_tile_name, new_drop_name, new_player_name, new_quantity, new_value):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE drops
            SET tile_name = %s, drop_name = %s, player_name = %s, drop_quantity = %s, drop_value = %s
            WHERE drops_pk = %s
        ''', (new_tile_name, new_drop_name, new_player_name, new_quantity, new_value, drop_pk))
        conn.commit()

def delete_drop(drop_pk):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM drops WHERE drops_pk = %s", (drop_pk,))
        conn.commit()


def get_relevant_drops_by_item_name_and_team_id(item, team_id):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM relevant_drops where team_id = %s and lower(drop_name) = lower(%s)", (team_id, item,))
        return cursor.fetchall()