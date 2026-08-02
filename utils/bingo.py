from collections import defaultdict

from utils import database, db_entities
from utils.db_entities import Drop


class TileProgress:
    def __init__(self):
        self.team = None
        self.tile = None
        self.status_text = "Something went wrong in calculating your progress. Please contact Danbis"
        self.progress_value = 0
        self.completions = 0



def get_drop_progress(tile_progress):
    tile_completion_count = tile_progress.completions
    tile = tile_progress.tile
    team = tile_progress.team
    triggers = tile.tile_triggers
    and_triggers = triggers.split(',')
    trigger_value = 0
    drops = defaultdict(int)
    for i in range(0, len(and_triggers)):
        trigger = and_triggers[i].strip()
        for or_trigger in trigger.split('/'):
            or_trigger = or_trigger.strip()
            for drop in database.get_drops_by_item_name_and_team_id(or_trigger, team.team_id):
                drop = db_entities.Drop(drop)
                drops[drop.drop_name] = drop.drop_quantity + drops[drop.drop_name]


        # if tile.tile_unique_drops == "True":
        #     if len(drops) > tile_completion_count:
        #         trigger_value = trigger_value + int(tile.tile_trigger_weights[i])
        #     continue
        # else:
        #     for drop in drops:
        #         drop = Drop(drop)
        #         trigger_value = int(tile.tile_trigger_weights[i]) * int(drop.drop_quantity) + trigger_value

    if tile.tile_unique_drops == "True":
        trigger_value = int(len(drops.values()))
    else:
        i = 0
        for name, quantity in drops.items():
            trigger_value = int(tile.tile_trigger_weights[i]) * int(quantity) + trigger_value

    trigger_value = (
        trigger_value
        + database.get_manual_progress_by_tile_id_and_team_id(
            tile.tile_id,
            team.team_id
        )
    )

    tile_progress.progress_value = (
        trigger_value % tile.tile_triggers_required
    )
    if tile_completion_count >= tile.tile_repetition:
        tile_progress.progress_value = tile.tile_triggers_required
        tile_progress.status_text = f"This tile is fully complete. You have {tile_progress.completions}/{tile_progress.tile.tile_repetition} completed."
    else:
        tile_progress.status_text = f"<p>You have {trigger_value % tile.tile_triggers_required} / {tile.tile_triggers_required} of the drops required to complete this tile."
    if len(drops) > 0:
        tile_progress.status_text += "Your current drops are: <ul>"
        for name, quantity in drops.items():
            tile_progress.status_text = tile_progress.status_text + "<li>" + str(quantity) + " x " + name.replace('\'', '') + "</li>"
        tile_progress.status_text = tile_progress.status_text + "</ul>"
    tile_progress.status_text += "</p>"
    return tile_progress


def get_set_progress(tile_progress):
    tile = tile_progress.tile
    team = tile_progress.team
    tile_completion_count = tile_progress.completions

    most_items_found = 0
    status_sections = []

    for item_set in tile.tile_triggers.split('/'):
        items = [
            item.strip()
            for item in item_set.split(',')
        ]

        missing_items = []
        items_found = 0

        for item in items:
            drops = (
                database
                .get_relevant_drops_by_item_name_and_team_id(
                    item,
                    team.team_id
                )
            )

            if len(drops) <= tile_completion_count:
                missing_items.append(item)
            else:
                items_found += 1

        most_items_found = max(
            most_items_found,
            items_found
        )

        if missing_items:
            status_sections.append(
                "Missing: " + ", ".join(missing_items)
            )

    if tile_completion_count >= tile.tile_repetition:
        tile_progress.progress_value = max(
            most_items_found,
            1
        )
        tile_progress.status_text = (
            "You have fully completed this tile!"
        )
    else:
        tile_progress.progress_value = most_items_found

        if status_sections:
            tile_progress.status_text = "\n".join(
                status_sections
            )
        else:
            tile_progress.status_text = (
                "No set progress has been recorded."
            )

    return tile_progress


def get_killcount_progress(tile_progress):

    tile = tile_progress.tile
    team = tile_progress.team
    tile_completion_count = tile_progress.completions

    if tile_completion_count >= tile.tile_repetition:
        tile_progress.progress_value = tile.tile_triggers_required
        tile_progress.status_text = (
            f"This tile is complete "
            f"({tile_completion_count}/{tile.tile_repetition} completions)."
        )
        return tile_progress

    trigger_value = 0

    for i, boss in enumerate(tile.tile_triggers.split(',')):
        kills = database.get_killcount_by_team_id_and_boss_name(
            team.team_id,
            boss.strip()
        )

        for kill in kills:
            kill = db_entities.Killcount(kill)
            trigger_value += (
                int(kill.kills)
                * int(tile.tile_trigger_weights[i])
            )

    trigger_value += (
        database.get_manual_progress_by_tile_id_and_team_id(
            tile.tile_id,
            team.team_id
        )
    )

    tile_progress.progress_value = (
        trigger_value % tile.tile_triggers_required
    )

    tile_progress.status_text = (
        f"You have {tile_progress.progress_value}/"
        f"{tile.tile_triggers_required} kills towards completing "
        f"this tile."
    )

    return tile_progress


def get_niche_progress(tile_progress):
    tile = tile_progress.tile
    team = tile_progress.team

    total_progress = (
        database.get_manual_progress_by_tile_id_and_team_id(
            tile.tile_id,
            team.team_id
        )
    )

    if tile_progress.completions >= tile.tile_repetition:
        tile_progress.progress_value = tile.tile_triggers_required
        tile_progress.status_text = (
            "You have fully completed this tile!"
        )
    else:
        tile_progress.progress_value = (
            total_progress % tile.tile_triggers_required
        )
        tile_progress.status_text = (
            f"You have {tile_progress.progress_value}/"
            f"{tile.tile_triggers_required} towards completing "
            f"this tile."
        )

    return tile_progress


def get_chat_progress(tile_progress):
    tile = tile_progress.tile
    team = tile_progress.team

    chats = database.get_chats_by_team_id_and_tile_id(
        team.team_id,
        tile.tile_id
    )

    total_progress = (
        len(chats)
        + database.get_manual_progress_by_tile_id_and_team_id(
            tile.tile_id,
            team.team_id
        )
    )

    if tile_progress.completions >= tile.tile_repetition:
        tile_progress.progress_value = tile.tile_triggers_required
        tile_progress.status_text = (
            "You have fully completed this tile!"
        )
    else:
        tile_progress.progress_value = (
            total_progress % tile.tile_triggers_required
        )
        tile_progress.status_text = (
            f"You have {tile_progress.progress_value}/"
            f"{tile.tile_triggers_required} towards completing "
            f"this tile."
        )

    return tile_progress


def get_pet_progress(tile_progress):
    tile = tile_progress.tile
    team = tile_progress.team

    total_pets = database.get_total_pets_by_team(
        team.team_id
    )

    if tile_progress.completions >= tile.tile_repetition:
        tile_progress.progress_value = tile.tile_triggers_required
        tile_progress.status_text = (
            "You have fully completed this tile!"
        )
    else:
        tile_progress.progress_value = (
            total_pets % tile.tile_triggers_required
        )
        tile_progress.status_text = (
            f"You have {tile_progress.progress_value}/"
            f"{tile.tile_triggers_required} pets towards completing "
            f"this tile."
        )

    return tile_progress


def get_progress(team_id, tile_id):
    tile_progress = TileProgress()

    team = database.get_team_by_id(team_id)
    if team is not None:
        tile_progress.team = db_entities.Team(team)

    tile = database.get_tile_by_id(tile_id)
    if tile is not None:
        tile_progress.tile = db_entities.Tile(tile)

    # Get the tile completions
    tile_progress.completions = len(database.get_completed_tiles_by_team_id_and_tile_id(tile_progress.team.team_id, tile_progress.tile.tile_id))

    # # If the tile has been completed more or equal to max allowed, return tile progress stating as such
    # if tile_progress.completions >= tile_progress.tile.tile_repetition:
    #     tile_progress.status_text = f"This tile is fully complete. You have {tile_progress.completions}/{tile_progress.tile.tile_repetition} completed."
    #     tile_progress.progress_value = 1
    #     return tile_progress

    if tile_progress.tile.tile_type == "DROP":
        return get_drop_progress(tile_progress)
    if tile_progress.tile.tile_type == "SET":
        return get_set_progress(tile_progress)
    if tile_progress.tile.tile_type == "KILLCOUNT":
        return get_killcount_progress(tile_progress)
    if tile_progress.tile.tile_type == "NICHE":
        return get_niche_progress(tile_progress)
    if tile_progress.tile.tile_type == "CHAT":
        return get_chat_progress(tile_progress)
    if tile_progress.tile.tile_type == "PET":
        return get_pet_progress(tile_progress)


# def check_progress(tile, team):
#     tile_completion_count = len(database.get_completed_tiles_by_team_id_and_tile_id(team.team_id, tile.tile_id))
#
#     if tile.tile_type == "DROP":
#         # Check if the tile was completed or if it was just progressing the tile
#         triggers = tile.tile_triggers
#         and_triggers = triggers.split(',')
#         trigger_value = int(database.get_manual_progress_by_tile_id_and_team_id(tile.tile_id, team.team_id))
#         drops_found = []
#         for i in range(0, len(and_triggers)):
#             # Check the current trigger adding up any or triggers into a cumulative variable list called "drops"
#             trigger = and_triggers[i].strip()
#             drops = []
#             for or_trigger in trigger.split('/'):
#                 or_trigger = or_trigger.strip()
#                 for drop in database.get_drops_by_item_name_and_team_id(or_trigger, team.team_id):
#                     drops.append(drop)
#
#             # If the tile is unique ignore quantity / duplicates
#             if tile.tile_unique_drops == "True":
#                 if len(drops) > tile_completion_count:
#                     trigger_value = trigger_value + int(tile.tile_trigger_weights[i])
#                     drops_found.append(or_trigger)
#                 continue
#             # else multiply the drop quantity for each drop by the trigger weight
#             else:
#                 for drop in drops:
#                     drop = Drop(drop)
#                     trigger_value = int(tile.tile_trigger_weights[i]) * int(drop.drop_quantity) + trigger_value
#         if trigger_value % tile.tile_triggers_required == 0:
#             return f"You have no progress on {tile.tile_name}"
#         result = f"{tile.tile_name} is {trigger_value % tile.tile_triggers_required} / {tile.tile_triggers_required} from being completed!\n"
#         if tile.tile_unique_drops == "True":
#             result = result + f"You have already found "
#             if len(drops_found) == 0:
#                 result = result + "- None"
#             else:
#                 for found in drops_found:
#                     result = result + "\n- " + found
#         if tile_completion_count > 0:
#             result = result + f"- You have completed this tile {tile_completion_count} times.\n"
#     if tile.tile_type == "SET":
#         # Each set is separated by a '/' character
#         result = ""
#         missing_items = []
#         for set in tile.tile_triggers.split('/'):
#             current_missing_set = []
#             for item in set.split(','):
#                 # Get the item name from the set and check if it exists in the db with the given team id
#                 item = item.strip()
#                 drops = database.get_drops_by_item_name_and_team_id(item, team.team_id)
#
#                 # If drops has a length of 0 nobody on the team has gotten this drop yet
#                 if len(drops) <= tile_completion_count:
#                     is_complete = False  # Flag the tile as incomplete
#                     current_missing_set.append(str(item))
#                     result = result + "-" + str(item) + "-"  # Add the missing item to the description
#             missing_items.append(current_missing_set)
#             # If is_complete is still true, every item from the set has been acquired and the tile is complete
#             result = f"For {tile.tile_name} you are missing:\n"
#             for sets in missing_items:
#                 result = result + "- "
#                 for item in sets:
#                     result = result + item + ", "
#                 result = result + "\n"
#     if tile.tile_type == "NICHE":
#         niche_progress = database.get_manual_progress_by_tile_name_and_team_name(tile.tile_name, team.team_name)
#         if tile_completion_count >= int(tile.tile_repetition):
#             result = f"You have fully completed {tile.tile_name}\n"
#         else:
#             result = f"You have completed {tile.tile_name} {tile_completion_count} times. You are {int(niche_progress % tile.tile_triggers_required)}/{tile.tile_triggers_required} from your next completion\n"
#     return result