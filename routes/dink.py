import os
import hashlib
import hmac
from collections import defaultdict

from flask import Blueprint, jsonify, request
import json

from utils import database, db_entities
from utils.db_entities import Player, Team, Tile, Drop
from utils.send_webhook import send_webhook

drop_submission_route = Blueprint("dink", __name__)


def create_dink_event_fingerprint(
    data,
    screenshot_sha256=None
):
    canonical_payload = json.dumps(
        data,
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=False
    )

    fingerprint_source = canonical_payload

    if screenshot_sha256 is not None:
        fingerprint_source += f":{screenshot_sha256}"

    return hashlib.sha256(
        fingerprint_source.encode('utf-8')
    ).hexdigest()


def get_uploaded_file_sha256(img_file):
    if img_file is None:
        return None

    img_file.stream.seek(0)
    file_bytes = img_file.stream.read()
    img_file.stream.seek(0)

    return hashlib.sha256(file_bytes).hexdigest()


def save_dink_evidence_screenshot(
    img_file,
    event_id
):
    if img_file is None:
        return None

    extension = os.path.splitext(
        img_file.filename or ''
    )[1].lower()

    allowed_extensions = {
        '.png',
        '.jpg',
        '.jpeg',
        '.webp'
    }

    if extension not in allowed_extensions:
        extension = '.png'

    project_root = os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )

    evidence_directory = os.path.join(
        project_root,
        'uploads',
        'dink_evidence'
    )

    os.makedirs(
        evidence_directory,
        exist_ok=True
    )

    filename = f'dink_event_{event_id}{extension}'

    absolute_path = os.path.join(
        evidence_directory,
        filename
    )

    img_file.stream.seek(0)
    img_file.save(absolute_path)
    img_file.stream.seek(0)

    return os.path.join(
        'uploads',
        'dink_evidence',
        filename
    )

def get_dink_auth_audit_details():
    request_format = 'OTHER'
    data = None

    if request.is_json:
        request_format = 'JSON'
        data = request.get_json(silent=True)

    elif request.mimetype == 'multipart/form-data':
        request_format = 'MULTIPART'

        json_data = request.form.get('payload_json')

        if json_data is not None:
            try:
                data = json.loads(json_data)
            except (json.JSONDecodeError, TypeError):
                data = None

    if not isinstance(data, dict):
        data = {}

    def get_claimed_text(field_name):
        value = data.get(field_name)

        if not isinstance(value, str):
            return None

        value = value.strip()

        if not value:
            return None

        return value[:255]

    return {
        'request_format': request_format,
        'claimed_player_name': get_claimed_text(
            'playerName'
        ),
        'claimed_dink_account_hash': get_claimed_text(
            'dinkAccountHash'
        ),
        'claimed_event_type': get_claimed_text(
            'type'
        )
    }


def record_dink_auth_failure(failure_reason):
    audit_details = get_dink_auth_audit_details()

    user_agent = request.user_agent.string

    if user_agent:
        user_agent = user_agent[:512]
    else:
        user_agent = None

    return database.record_dink_auth_failure(
        failure_reason=failure_reason,
        request_format=audit_details['request_format'],
        claimed_player_name=(
            audit_details['claimed_player_name']
        ),
        claimed_dink_account_hash=(
            audit_details['claimed_dink_account_hash']
        ),
        claimed_event_type=(
            audit_details['claimed_event_type']
        ),
        source_ip=request.remote_addr,
        user_agent=user_agent
    )


def is_valid_dink_ingest_secret(provided_secret):
    expected_secret = os.getenv('DINK_INGEST_SECRET')

    if not expected_secret:
        return False, 'SERVER_MISCONFIGURED'

    if provided_secret is None:
        return False, 'MISSING_SECRET'

    if not hmac.compare_digest(
        provided_secret,
        expected_secret
    ):
        return False, 'INVALID_SECRET'

    return True, None


def get_dink_request_payload():
    img_file = request.files.get('file')

    if request.is_json:
        data = request.get_json(silent=True)

        if not isinstance(data, dict):
            raise ValueError(
                "Dink JSON payload must be an object"
            )

        return data, img_file

    json_data = request.form.get('payload_json')

    if json_data is None:
        raise ValueError(
            "Request did not contain a Dink payload"
        )

    data = json.loads(json_data)

    if not isinstance(data, dict):
        raise ValueError(
            "Dink payload_json must contain a JSON object"
        )

    return data, img_file

def get_dink_event_progress(data):
    event_type = str(
        data.get('type', '')
    ).strip().upper()

    extra = data.get('extra')

    if not isinstance(extra, dict):
        return []

    if event_type == 'LOOT':
        items = extra.get('items')

        if not isinstance(items, list):
            raise ValueError(
                "Dink LOOT payload did not contain a valid items list"
            )

        progress_items = []

        for item in items:
            if not isinstance(item, dict):
                raise ValueError(
                    "Dink LOOT payload contained an invalid item"
                )

            item_name = item.get('name')
            quantity = item.get('quantity', 1)

            if not isinstance(item_name, str) or not item_name.strip():
                raise ValueError(
                    "Dink LOOT item did not contain a valid name"
                )

            try:
                quantity = int(quantity)
            except (TypeError, ValueError):
                raise ValueError(
                    f"Dink LOOT item {item_name} "
                    f"contained an invalid quantity"
                )

            if quantity < 1:
                raise ValueError(
                    f"Dink LOOT item {item_name} "
                    f"contained an invalid quantity"
                )

            progress_items.append(
                {
                    "condition_type": "DROP",
                    "trigger": item_name.strip(),
                    "amount": quantity
                }
            )

        return progress_items

    if event_type == 'PET':
        pet_name = extra.get('petName')

        if not isinstance(pet_name, str) or not pet_name.strip():
            raise ValueError(
                "Dink PET payload did not contain a valid petName"
            )

        return [
            {
                "condition_type": "PET",
                "trigger": pet_name.strip(),
                "amount": 1
            }
        ]

    return []

def cleanup_ignored_dink_event(event_id):
    screenshot_path = database.minimise_ignored_dink_event(
        event_id
    )

    if not screenshot_path:
        return

    project_root = os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )

    screenshot_file = os.path.join(
        project_root,
        screenshot_path
    )

    try:
        if os.path.isfile(screenshot_file):
            os.remove(screenshot_file)

        database.clear_dink_event_screenshot_path(
            event_id
        )
    except OSError as e:
        print(
            f"Unable to delete ignored Dink screenshot "
            f"{screenshot_file}: {e}"
        )

def process_pending_dink_events(
    dink_account_hash,
    player_id
):
    pending_events = (
        database.get_pending_dink_events_by_hash(
            dink_account_hash
        )
    )

    processed_events = []

    for (
        event_id,
        event_type,
        raw_payload,
        received_at
    ) in pending_events:
        event_progress = get_dink_event_progress(
            raw_payload
        )

        result = database.process_dink_event_progress(
            event_id=event_id,
            player_id=player_id,
            event_progress=event_progress
        )

        if result["status"] == "IGNORED":
            cleanup_ignored_dink_event(
                event_id
            )

        processed_events.append(
            {
                "event_id": event_id,
                "event_type": event_type,
                "received_at": received_at,
                "result": result
            }
        )

    return processed_events

def ingest_dink_event(data, img_file=None):
    player_name = data.get('playerName')
    dink_account_hash = data.get('dinkAccountHash')
    event_type = data.get('type')

    if not isinstance(player_name, str) or not player_name.strip():
        raise ValueError(
            "Dink payload did not contain a valid playerName"
        )

    if (
        not isinstance(dink_account_hash, str)
        or not dink_account_hash.strip()
    ):
        raise ValueError(
            "Dink payload did not contain a valid dinkAccountHash"
        )

    player_name = player_name.strip()
    dink_account_hash = dink_account_hash.strip()

    screenshot_sha256 = get_uploaded_file_sha256(
        img_file
    )

    event_fingerprint = create_dink_event_fingerprint(
        data,
        screenshot_sha256
    )

    recent_event = (
        database.get_recent_dink_event_by_fingerprint(
            event_fingerprint
        )
    )

    if recent_event is not None:
        (
            original_event_id,
            _,
            original_status,
            original_player_id,
            original_dink_account_hash
        ) = recent_event

        event_id = database.add_dink_event(
            event_fingerprint=event_fingerprint,
            raw_payload=data,
            dink_account_hash=dink_account_hash,
            player_name=player_name,
            event_type=event_type,
            duplicate_of_event_id=original_event_id,
            status='IGNORED'
        )

        cleanup_ignored_dink_event(
            event_id
        )

        if (
            original_status == 'RECEIVED'
            and original_player_id is not None
            and original_dink_account_hash == dink_account_hash
        ):
            return {
                'event_id': event_id,
                'processing_event_id': original_event_id,
                'status': 'RETRY',
                'player_id': original_player_id,
                'observations': (
                    database.count_dink_hash_observations(
                        dink_account_hash
                    )
                )
            }

        return {
            'event_id': event_id,
            'processing_event_id': None,
            'status': 'DUPLICATE',
            'player_id': None,
            'observations': None
        }

    event_id = database.add_dink_event(
        event_fingerprint=event_fingerprint,
        raw_payload=data,
        dink_account_hash=dink_account_hash,
        player_name=player_name,
        event_type=event_type
    )

    if img_file is not None:
        screenshot_path = save_dink_evidence_screenshot(
            img_file,
            event_id
        )

        database.update_dink_event_screenshot(
            event_id,
            screenshot_path,
            screenshot_sha256
        )

    identity = database.get_dink_identity_by_hash(
        dink_account_hash
    )

    # Once a Dink hash is linked, the hash becomes the stable
    # identity rather than relying on the player's current RSN.
    if identity is not None and identity[3] == 'LINKED':
        player_id = identity[1]

        database.update_dink_event_identity(
            event_id,
            player_id,
            'RECEIVED'
        )

        return {
            'event_id': event_id,
            'status': 'LINKED',
            'player_id': player_id,
            'observations': (
                database.count_dink_hash_observations(
                    dink_account_hash
                )
            )
        }

    identity_status = database.record_pending_dink_identity(
        dink_account_hash,
        player_name
    )

    if identity_status == 'CONFLICT':
        database.update_dink_event_identity(
            event_id,
            None,
            'PENDING_IDENTITY'
        )

        return {
            'event_id': event_id,
            'status': 'CONFLICT',
            'player_id': None,
            'observations': None
        }

    link_result = database.try_link_dink_identity(
        dink_account_hash,
        player_name
    )

    if link_result['status'] == 'LINKED':
        database.update_dink_event_identity(
            event_id,
            link_result['player_id'],
            'RECEIVED'
        )

        process_pending_dink_events(
            dink_account_hash,
            link_result['player_id']
        )

    else:
        database.update_dink_event_identity(
            event_id,
            None,
            'PENDING_IDENTITY'
        )

    return {
        'event_id': event_id,
        'status': link_result['status'],
        'player_id': link_result['player_id'],
        'observations': link_result['observations']
    }


# function to parse death data
def parse_death(data) -> dict[str, list[str]]:
    rsn = data['playerName']
    # Check if killerName exists
    if 'killerName' not in data['extra']:
        print("DEATH: " + rsn)
    else:
        print("DEATH: " + rsn + " died to " + data['extra']['killerName'])
    database.add_death_by_playername(rsn)
    # print data prettyfied
    # print(json.dumps(data, indent = 2))
    return True


# function to parse collection data
def parse_collection(data) -> dict[str, list[str]]:
    rsn = data['playerName']
    itemName = data['extra']['itemName']
    print(f"COLLECTION - {rsn} got a new collection log {itemName}")
    return True


# function to parse level data
def parse_level(data) -> dict[str, list[str]]:
    rsn = data['playerName']
    levelledSkills = data['extra']['levelledSkills']
    print(f"LEVEL - {rsn} levelled up {levelledSkills}")
    return True


def parse_loot(data, img_file) -> dict[str, list[str]]:

    # Get rsn
    rsn = data['playerName']

    # Handle discord attachment
    player = database.get_player_by_name(rsn)
    if player is None:
        return False
    player = db_entities.Player(player)

    team = database.get_team_by_id(player.team_id)
    if team is None:
        return False
    team = db_entities.Team(team)

    source = data['extra']['source']
    # Get item source
    itemSource = data['extra']['source']

    # Get item list
    items = data['extra']['items']
    # Loop through items
    for item in items:
        # Get item name
        itemName = item['name']
        # Get item price
        itemPrice = item['priceEach']
        # Get item quantity
        itemQuantity = item['quantity']
        # Get item total
        item_each = item['priceEach']

        # Add the item to the database
        print(f"LOOT: {player.player_name} - {itemName} x {itemQuantity} ({itemQuantity * itemPrice})")
        drop_pk = database.add_drop(team.team_id, player.player_id, rsn, itemName, item_each, itemQuantity, itemSource)

        # If the item is relevant
        if database.get_drop_whitelist_by_item_name(itemName) is not None:
            # Find the tile and team associated with this player / drop
            tile = Tile(database.get_tile_by_drop(itemName))
            team = Team(database.get_team_by_id(team.team_id))
            description = ""
            tile_completion_count = len(database.get_completed_tiles_by_team_id_and_tile_id(team.team_id, tile.tile_id))
            color = 0

            # Drop tile logic
            if tile.tile_type == "DROP":
                # If the tile has been completed too many times do nothing
                if tile_completion_count >= 1:
                    continue

                database.add_relevant_drop(team.team_id, player.player_id, tile.tile_id, tile.tile_name, itemName, player.player_name, drop_pk)
                # Find the weight of the trigger and add the proportion to the players tile completions
                for i in range(len(tile.tile_triggers.split(','))):
                    for trigger in tile.tile_triggers.split(',')[i].split('/'):
                        if itemName == trigger.strip():
                            database.add_player_partial_completions(player.player_id, team.team_id, tile.tile_id, (int(tile.tile_trigger_weights[i]) * int(itemQuantity)) / tile.tile_triggers_required)
                # Check if the tile was completed or if it was just progressing the tile
                triggers = tile.tile_triggers
                and_triggers = triggers.split(',')
                trigger_value = database.get_manual_progress_by_tile_id_and_team_id(tile.tile_id, team.team_id)
                for i in range(0, len(and_triggers)):
                    # Check the current trigger adding up any or triggers into a cumulative variable list called "drops"
                    trigger = and_triggers[i].strip()
                    drops = []
                    for or_trigger in trigger.split('/'):
                        or_trigger = or_trigger.strip()
                        for drop in database.get_drops_by_item_name_and_team_id(or_trigger, team.team_id):
                            drops.append(drop)

                    # If the tile is unique ignore quantity / duplicates
                    if tile.tile_unique_drops == "True":
                        if len(drops) > 0:
                            trigger_value = trigger_value + int(tile.tile_trigger_weights[i])
                        continue
                    # else multiply the drop quantity for each drop by the trigger weight
                    else:
                        for drop in drops:
                            drop = Drop(drop)
                            trigger_value = int(tile.tile_trigger_weights[i]) * int(drop.drop_quantity) + trigger_value

                # If the trigger value is greater than triggers required multiplied by tile completion count then the tile has been completed an additional time
                if trigger_value >= tile.tile_triggers_required * (tile_completion_count + 1):# or (tile.tile_unique_drops == "True" and trigger_value >= tile.tile_triggers_required):
                    description = f"{tile.tile_name} completed! Congratulations! Your team has been awarded {tile.tile_points} point(s)!"
                    database.add_completed_tile(tile.tile_id, team.team_id)
                    description = description + f"\nYou have completed this tile {tile_completion_count + 1} times."
                    color = 65280 # Green
                    database.add_team_points(team.team_id, tile.tile_points)
                    current_trigger_rewards = 0
                    # Award partial_completions as full tile completions
                    for partial_completion in database.get_partial_completions_by_team_id_and_tile_id(team.team_id,
                                                                                                      tile.tile_id):
                        partial_completion = db_entities.PartialCompletion(partial_completion)
                        database.remove_partial_completion(partial_completion.partial_completion_pk)
                        credited_completion = min(
                            partial_completion.partial_completion,
                            1 - current_trigger_rewards
                        )
                        database.add_player_tile_completions(
                            partial_completion.player_id,
                            credited_completion
                        )
                        current_trigger_rewards += credited_completion
                # Otherwise this drop only progressed the tile and didn't complete it
                else:
                    description = f"{tile.tile_name} is {trigger_value % tile.tile_triggers_required} / {tile.tile_triggers_required} from being completed!"
                    if tile_completion_count > 0:
                        description = description + f"\nYou have completed this tile {tile_completion_count} times."
                    color = 16776960 # Yellow

            # Set logic
            elif tile.tile_type == "SET":
                # If the tile has been completed too many times do nothing
                if tile_completion_count >= tile.tile_repetition:
                    continue

                database.add_relevant_drop(team.team_id, player.player_id, tile.tile_id, tile.tile_name, itemName, player.player_name, drop_pk)
                color = 16776960 # Yellow by default
                description = "You are still missing\n" # Assume set is not completed
                missing_items = []


                # Each set is separated by a '/' character
                for set in tile.tile_triggers.split('/'):
                    # If the item belongs to the current set, add 1 / the set length to the players tile completions
                    if itemName.lower() in set.lower():
                        database.add_player_partial_completions(player.player_id, team.team_id, tile.tile_id, 1 / len(set.split(',')))

                    # If every item from the set is found in the db is_complete will remain True
                    # Iterate through every item in the set (separated by ',') and check if the players team has at least one in the db
                    is_complete = True
                    current_missing_set = []
                    for item in set.split(','):
                        # Get the item name from the set and check if it exists in the db with the given team id
                        item = item.strip()
                        drops = database.get_drops_by_item_name_and_team_id(item, team.team_id)

                        # If drops has a length of 0 nobody on the team has gotten this drop yet
                        if len(drops) <= tile_completion_count:
                            is_complete = False                                 # Flag the tile as incomplete
                            current_missing_set.append(str(item))
                            description = description + "-" + str(item) + "-"   # Add the missing item to the description
                    missing_items.append(current_missing_set)
                    # If is_complete is still true, every item from the set has been acquired and the tile is complete
                    if is_complete:
                        description = f"{tile.tile_name} is completed! {team.team_name} has been awarded {tile.tile_points}\n points!"
                        color = 65280 # Green
                        database.add_team_points(team.team_id, tile.tile_points)
                        database.add_completed_tile(tile.tile_id, team.team_id)
                        for partial_completion in database.get_partial_completions_by_team_id_and_tile_id(team.team_id,
                                                                                                          tile.tile_id):
                            partial_completion = db_entities.PartialCompletion(partial_completion)
                            database.remove_partial_completion(partial_completion.partial_completion_pk)
                            database.add_player_tile_completions(partial_completion.player_id,
                                                                 partial_completion.partial_completion)
                        break
                    else:
                        description = "You are still missing\n"
                        for sets in missing_items:
                            description = description + "- "
                            for item in sets:
                                description = description + item + ", "
                            description = description + "\n"
            # Green = 65280, Yellow = 16776960
            # Alert the team of either their progress or their tile completion
            send_webhook(team.team_webhook, title=f"{rsn} got a {itemName} from {source}!", description=description, color=color, image=img_file)

    # Return true to signify the drop has been properly processed with no error
    return True


# function to parse slayer data
def parse_slayer(data) -> dict[str, list[str]]:
    rsn = data['playerName']
    slayer_monster = data['extra']['monster']
    kc_required = data['extra']['killCount']

    print(f"SLAYER - {rsn} finished their {slayer_monster} task ({kc_required} kill(s))")
    # print data prettyfied
    # print(json.dumps(data, indent = 2))
    return False


# function to parse quest data
def parse_quest(data) -> dict[str, list[str]]:
    rsn = data['playerName']
    questName = data['extra']['questName']

    print(f"QUEST - {rsn} completed {questName}")

    return True


# function to parse clue data
def parse_clue(data):
    rsn = data['playerName']
    clueType = data['extra']['clueType']

    print(f"CLUE: {rsn} - {clueType}")
    return True


# function to parse kill count data
def parse_kill_count(data, img_file) -> dict[str, list[str]]:
    rsn = data['playerName']
    boss_name = data['extra']['boss']
    print(f"KILLCOUNT: {rsn} - {boss_name}")

    try:
        quantity = data['extra']['quantity']
    except:
        quantity = 1

    player = database.get_player_by_name(rsn)
    if player is None:
        return False
    player = db_entities.Player(player)
    player_id = player.player_id

    team = database.get_team_by_id(player.team_id)
    if team is None:
        return False
    team = db_entities.Team(team)
    team_id = team.team_id

    database.add_killcount(player_id, team_id, boss_name, quantity)
    if database.get_drop_whitelist_by_item_name(boss_name) is not None:
        tile = Tile(database.get_tile_by_drop(boss_name))
        team = Team(database.get_team_by_id(team_id))
        tile_completion_count = len(database.get_completed_tiles_by_team_id_and_tile_id(team_id, tile.tile_id))

        if tile_completion_count >= 1:
            return True

        killcount_weights = defaultdict(int)
        for i in range(len(tile.tile_trigger_weights)):
            killcount_weights[tile.tile_triggers.split(',')[i].strip().lower()] = int(tile.tile_trigger_weights[i])

        database.add_player_partial_completions(player_id, team.team_id, tile.tile_id, (killcount_weights[boss_name.lower()] * quantity) / tile.tile_triggers_required)
        team_killcount = database.get_manual_progress_by_tile_id_and_team_id(tile.tile_id, team.team_id)
        total_killcount = []
        for boss_trigger in tile.tile_triggers.split(','):
            killcounts = database.get_killcount_by_team_id_and_boss_name(team.team_id, boss_trigger.strip())
            for killcount in killcounts:
                killcount = db_entities.Killcount(killcount)
                total_killcount.append(killcount)
                team_killcount = team_killcount + (killcount.kills * killcount_weights[killcount.boss_name.lower()])

        if team_killcount >= tile.tile_triggers_required * (tile_completion_count + 1):
            database.add_completed_tile(tile.tile_id, team_id)
            database.add_team_points(team_id, tile.tile_points)
            description = (f"You have completed {tile.tile_name}! You have {tile_completion_count + 1} total completions"
                           f" with the following killcount\n")
            for killcount in total_killcount:
                player_ = database.get_player_by_id(killcount.player_id)
                player_ = db_entities.Player(player_)
                description = description + f"- {player_.player_name} with {killcount.kills} {killcount.boss_name} kills\n"
            send_webhook(team.team_webhook, f"{tile.tile_name} completed!", description=description,
                         color=65280, image=img_file)
            # Todo update player tile completions based on partial tile completion table
            current_trigger_rewards = 0
            for partial_completion in database.get_partial_completions_by_team_id_and_tile_id(team.team_id,
                                                                                              tile.tile_id):
                partial_completion = db_entities.PartialCompletion(partial_completion)
                database.remove_partial_completion(partial_completion.partial_completion_pk)
                database.add_player_tile_completions(partial_completion.player_id,
                                                     min(partial_completion.partial_completion,
                                                         1 - current_trigger_rewards))
                credited_completion = min(
                    partial_completion.partial_completion,
                    1 - current_trigger_rewards
                )
                current_trigger_rewards += credited_completion
        elif boss_name.lower() == "TzTok-Jad".lower() or boss_name.lower() == "TzTok-Zuk".lower() or boss_name.lower() == "Sol-Heredit".lower():
            send_webhook(team.team_webhook, f"{player.player_name} killed {boss_name}! You are {(team_killcount % tile.tile_triggers_required)}/{tile.tile_triggers_required} from completing {tile.tile_name}",
                         description="", color=16776960, image=img_file)
            drop_name = ""
            if boss_name.lower() == "TzTok-Jad".lower():
                drop_name = "Fire cape"
            if boss_name.lower() == "TzTok-Zuk".lower():
                drop_name = "Infernal cape"
            if boss_name.lower() == "Sol-Heredit".lower():
                drop_name = "Dizana's quiver"
            drop_pk = database.add_drop(team.team_id, player.player_id, player.player_name, drop_name, 0, 1, boss_name.lower())
            database.add_relevant_drop(team.team_id, player.player_id, tile.tile_id, tile.tile_name, boss_name, player.player_name, drop_pk)
    return True


# function to parse combat achievement data
def parse_combat_achievement(data) -> dict[str, list[str]]:
    # print data prettyfied
    # print(json.dumps(data, indent = 2))
    rsn = data['playerName']
    achievement = data['extra']['task']
    tier = data['extra']['tier']

    print("COMBAT_ACHIEVEMENT: " + rsn + " - " + achievement + " (" + tier + ")")
    return []


# function to parse pet data
def parse_pet(data, img_file) -> dict[str, list[str]]:
    screenshotItems: dict[str, list[str]] = {}
    # print data prettyfied
    rsn = data['playerName']
    pet = data['extra']['petName']
    print(f"PET: {rsn} - {pet}")

    PET_POINTS = 0.5
    black_listed_pets = []

    player = database.get_player_by_name(rsn)
    if player is not None:
        player = db_entities.Player(player)
    else:
        return False

    team = database.get_team_by_id(player.team_id)
    team = db_entities.Team(team)
    database.add_pet_by_playername(rsn)

    # If a pet tile exists change behavior based on tile input
    pet_tile = database.get_tile_by_type("PET")
    if len(pet_tile) > 0:
        pet_tile = db_entities.Tile(pet_tile[0])
        tile_completion_count = len(database.get_completed_tiles_by_team_id_and_tile_id(team.team_id, pet_tile.tile_id))
        if pet in [trigger.strip() for trigger in pet_tile.tile_triggers.split(',')] or tile_completion_count >= 1:
            send_webhook(team.team_webhook, f"{player.player_name} is being followed by {pet}!", description="Too bad its not worth any points....", color=16776960, image=img_file)
        else:
            database.add_player_tile_completions(player.player_id, 1)
            database.add_team_points(team.team_id, pet_tile.tile_points)
            database.add_completed_tile(pet_tile.tile_id, team.team_id)
            send_webhook(team.team_webhook, f"{player.player_name} is being followed by {pet}!", description=f"{team.team_name} has been awarded {pet_tile.tile_points} points!", color=65280, image=img_file)

    # If no pet tile exists, default setup configured here
    else:
        if pet in black_listed_pets:
            send_webhook(team.team_webhook, f"{player.player_name} is being followed by {pet}!",
                         description="Too bad its not worth any points....", color=16776960, image=img_file)
        else:
            database.add_player_tile_completions(player.player_id, 1)
            database.add_team_points(team.team_id, PET_POINTS)
            send_webhook(team.team_webhook, f"{player.player_name} is being followed by {pet}!", description=f"{team.team_name} has been awarded {PET_POINTS} points!", color=65280, image=img_file)

    return True


# function to parse speedrun data
def parse_speedrun(data) -> dict[str, list[str]]:
    # print("SPEEDRUN")
    # print data prettyfied
    # print(json.dumps(data, indent = 2))
    return False


# function to parse barbarian assault gamble data
def parse_barbarian_assault_gamble(data) -> dict[str, list[str]]:
    # print("BARBARIAN_ASSAULT_GAMBLE")
    # print data prettyfied
    # print(json.dumps(data, indent = 2))
    return True


# function to parse player kill data
def parse_player_kill(data) -> dict[str, list[str]]:
    rsn = data['playerName']
    victim = data['extra']['victimName']
    print(f"PLAYER_KILL - {rsn} killed {victim}")
    # print data prettyfied
    # print(json.dumps(data, indent = 2))
    return True


# function to parse group storage data
def parse_group_storage(data) -> dict[str, list[str]]:
    # print("GROUP_STORAGE")
    # print data prettyfied
    # print(json.dumps(data, indent = 2))
    return True


# function to parse grand exchange data
def parse_grand_exchange(data) -> dict[str, list[str]]:
    # print("GRAND_EXCHANGE")
    # print data prettyfied
    # print(json.dumps(data, indent = 2))
    return True


# function to parse trade data
def parse_trade(data) -> dict[str, list[str]]:
    rsn = data['playerName']
    other_rsn = data['extra']['counterparty']

    print(f"TRADE - {rsn} and {other_rsn}")
    rsn_recieved_list = []
    for receivedItem in data['extra']['receivedItems']:
        rsn_recieved_list.append(f"{receivedItem['name']} x {receivedItem['quantity']},")
    print(f"{rsn} received: {rsn_recieved_list}")
    other_received_list = []
    for other_received in data['extra']['givenItems']:
        other_received_list.append(f"{other_received['name']} x {other_received['quantity']},")
    print(f"{other_rsn} received: {other_received_list}")

    return True

# function to delegate parsing to its own function basing on the 'type' data
def parse_chat(data, img_file):
    rsn = data['playerName']
    chat_text = data['extra']['message']
    print(f"CHAT: {rsn} - \"{chat_text}\"")

    tile = database.get_tile_by_drop(chat_text)
    if tile is None:
        return False
    tile = db_entities.Tile(tile)

    player = database.get_player_by_name(rsn)
    if player is None:
        return False
    player = db_entities.Player(player)

    team = database.get_team_by_id(player.team_id)
    if team is None:
        return False
    team = db_entities.Team(team)

    tile_completions = len(
        database.get_completed_tiles_by_team_id_and_tile_id(
            team.team_id,
            tile.tile_id
        )
    )

    if tile_completions >= 1:
        return False

    database.add_chats(player.player_id, team.team_id, tile.tile_id, chat_text)
    database.add_player_partial_completions(player.player_id, team.team_id, tile.tile_id, int(tile.tile_trigger_weights[0]) / tile.tile_triggers_required)

    total_chats = len(database.get_chats_by_team_id_and_tile_id(team.team_id, tile.tile_id))
    if total_chats >= tile.tile_triggers_required * (tile_completions + 1):
        database.add_completed_tile(tile.tile_id, team.team_id)
        database.add_team_points(team.team_id, tile.tile_points)
        send_webhook(team.team_webhook, title=f"{player.player_name} finished {tile.tile_name}!", description=f"", color=65280, image=img_file)
        for partial_completion in database.get_partial_completions_by_team_id_and_tile_id(team.team_id, tile.tile_id):
            partial_completion = db_entities.PartialCompletion(partial_completion)
            database.remove_partial_completion(partial_completion.partial_completion_pk)
            database.add_player_tile_completions(partial_completion.player_id, partial_completion.partial_completion)
            if chat_text == "You are victorious!":
                database.add_relevant_drop(
                    team.team_id,
                    player.player_id,
                    tile.tile_id,
                    tile.tile_name,
                    "LMS Win",
                    player.player_name,
                    None
                )
    else:
        send_webhook(team.team_webhook, title=f"{tile.tile_name} progress!", description=f"Thanks to {player.player_name}, you are {total_chats % tile.tile_triggers_required}/{tile.tile_triggers_required} from completing this tile", color=16776960, image=img_file )

    return True

# function to parse leagues area data
def parse_leagues_area(data) -> dict[str, list[str]]:
    # print("LEAGUES_AREA")
    # print data prettyfied
    # print(json.dumps(data, indent = 2))
    return True


# function to parse leagues relic data
def parse_leagues_relic(data) -> dict[str, list[str]]:
    # print("LEAGUES_RELIC")
    # print data prettyfied
    # print(json.dumps(data, indent = 2))
    return True


# function to parse leagues task data
def parse_leagues_task(data) -> dict[str, list[str]]:
    # print("LEAGUES_TASK")
    # print data prettyfied
    # print(json.dumps(data, indent = 2))
    return True


# function to parse login data
def parse_login(data) -> dict[str, list[str]]:
    rsn = data['playerName']
    print(f"LOGIN - {rsn}")

    return True





def parse_json_data(json_data, img_file) -> dict[str, list[str]]:
    data = json.loads(json_data)

    # types are: 'DEATH', 'COLLECTION, 'LEVEL', 'LOOT', 'SLAYER', 'QUEST',
    # 'CLUE', 'KILL_COUNT', 'COMBAT_ACHIEVEMENT', 'PET', 'SPEEDRUN', 'BARBARIAN_ASSAULT_GAMBLE',
    # 'PLAYER_KILL', 'GROUP_STORAGE', 'GRAND_EXCHANGE', 'TRADE', 'LEAGUES_AREA', 'LEAGUES_RELIC',
    # 'LEAGUES_TASK', and 'LOGIN'

    if 'type' in data:
        type = data['type']
        if type == 'DEATH':
            return parse_death(data)
        elif type == 'COLLECTION':
            return parse_collection(data)
        elif type == 'LEVEL':
            return parse_level(data)
        elif type == 'LOOT':
            return parse_loot(data, img_file)
        elif type == 'SLAYER':
            return parse_slayer(data)
        elif type == 'QUEST':
            return parse_quest(data)
        elif type == 'CLUE':
            return parse_clue(data)
        elif type == 'KILL_COUNT':
            return parse_kill_count(data, img_file)
        elif type == 'COMBAT_ACHIEVEMENT':
            return parse_combat_achievement(data)
        elif type == 'PET':
            return parse_pet(data, img_file)
        elif type == 'SPEEDRUN':
            return parse_speedrun(data)
        elif type == 'BARBARIAN_ASSAULT_GAMBLE':
            return parse_barbarian_assault_gamble(data)
        elif type == 'PLAYER_KILL':
            return # parse_player_kill(data)
        elif type == 'GROUP_STORAGE':
            return parse_group_storage(data)
        elif type == 'GRAND_EXCHANGE':
            return parse_grand_exchange(data)
        elif type == 'TRADE':
            return parse_trade(data)
        elif type == 'CHAT':
            return parse_chat(data, img_file)
        elif type == 'LEAGUES_AREA':
            return parse_leagues_area(data)
        elif type == 'LEAGUES_RELIC':
            return parse_leagues_relic(data)
        elif type == 'LEAGUES_TASK':
            return parse_leagues_task(data)
        elif type == 'LOGIN':
            return parse_login(data)
        else:
            print(f"Unknown type: {type}")
    else:
        print(f"Unknown data: {data}")

    return []



@drop_submission_route.route(
    '',
    defaults={'provided_secret': None},
    methods=['POST']
)
@drop_submission_route.route(
    '/<provided_secret>',
    methods=['POST']
)
def handle_request(provided_secret):
    is_authorised, failure_reason = (
        is_valid_dink_ingest_secret(
            provided_secret
        )
    )

    if not is_authorised:
        try:
            record_dink_auth_failure(
                failure_reason
            )
        except Exception as e:
            print(
                "Failed to record Dink auth failure: "
                f"{e}"
            )

        return jsonify({
            "message": "Not found"
        }), 404

    if os.getenv('TRACKING') == "FALSE":
        return jsonify({
            "message": "Not currently tracking"
        })

    try:
        data, img_file = get_dink_request_payload()

        ingestion_result = ingest_dink_event(
            data,
            img_file
        )

        processing_result = None

        if ingestion_result["status"] in (
            "LINKED",
            "RETRY"
        ):
            event_progress = get_dink_event_progress(
                data
            )

            processing_event_id = (
                ingestion_result.get("processing_event_id")
                or ingestion_result["event_id"]
            )

            processing_result = (
                database.process_dink_event_progress(
                    event_id=processing_event_id,
                    player_id=ingestion_result["player_id"],
                    event_progress=event_progress
                )
            )

            if processing_result["status"] == "IGNORED":
                cleanup_ignored_dink_event(
                    processing_event_id
                )

    except ValueError as e:
        print(f"Invalid Dink request: {e}")

        return jsonify({
            "message": str(e)
        }), 400

    except Exception as e:
        print(f"Error ingesting Dink request: {e}")

        return jsonify({
            "message": "Error ingesting Dink request"
        }), 500

    return jsonify({
        "message": "Dink event received",
        "event_id": ingestion_result["event_id"],
        "identity_status": ingestion_result["status"],
        "observations": ingestion_result["observations"],
        "processing_status": (
            processing_result["status"]
            if processing_result is not None
            else None
        )
    })