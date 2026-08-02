class Player:
    def __init__(self, player_tuple):
        self.player_id = player_tuple[0]
        self.player_name = player_tuple[1]
        self.deaths = player_tuple[2]
        self.gp_gained = player_tuple[3]
        self.tiles_completed = player_tuple[4]
        self.team_id = player_tuple[5]
        self.pet_count = player_tuple[6]
        self.discord_user_id = player_tuple[7] if len(player_tuple) > 7 else None


class Team:
    def __init__(self, team_tuple):
        self.team_name = team_tuple[0]
        self.team_points = team_tuple[1]
        self.team_webhook = team_tuple[2]
        self.team_id = team_tuple[3]
        self.discord_role_id = team_tuple[4] if len(team_tuple) > 4 else None


class Drop:
    def __init__(self, drop_tuple):
        self.team_id = drop_tuple[0]
        self.player_id = drop_tuple[1]
        self.player_name = drop_tuple[2]
        self.drop_name = drop_tuple[3]
        self.drop_value = drop_tuple[4]
        self.drop_quantity = drop_tuple[5]
        self.drop_source = drop_tuple[6]
        self.drop_pk = drop_tuple[7]


class Killcount:
    def __init__(self, killcount_tuple):
        self.player_id = killcount_tuple[0]
        self.team_id = killcount_tuple[1]
        self.boss_name = killcount_tuple[2]
        self.kills = killcount_tuple[3]


class DropWhitelist:
    def __init__(self, drop_whitelist_tuple):
        self.drop_name = drop_whitelist_tuple[0]


class CompletedTile:
    def __init__(self, completed_tile_tuple):
        self.team_id = completed_tile_tuple[0]
        self.tile_id = completed_tile_tuple[1]
        self.completed_tile_pk = completed_tile_tuple[2]


class Tile:
    def __init__(self, tile_tuple):
        self.tile_id = tile_tuple[0]
        self.tile_name = tile_tuple[1]
        self.tile_type = tile_tuple[2]
        self.tile_triggers = tile_tuple[3]
        if tile_tuple[4] is not None:
            self.tile_trigger_weights = tile_tuple[4].split(',')
        else:
            self.tile_trigger_weights = None
        self.tile_unique_drops = str(tile_tuple[5])
        self.tile_triggers_required = tile_tuple[6]
        self.tile_repetition = tile_tuple[7]
        self.tile_points = tile_tuple[8]
        self.tile_rules = tile_tuple[9]


class Request:
    def __init__(self, request_tuple):
        self.request_id = request_tuple[0],
        self.team_name = request_tuple[1],
        self.player_name = request_tuple[2],
        self.tile_name = request_tuple[3],
        self.item_name = request_tuple[4]
        self.evidence = request_tuple[5]


class PartialCompletion:
    def __init__(self, partial_completion_tuple):
        self.team_id = partial_completion_tuple[0]
        self.tile_id = partial_completion_tuple[1]
        self.player_id = partial_completion_tuple[2]
        self.partial_completion = partial_completion_tuple[3]
        self.partial_completion_pk = partial_completion_tuple[4]


class RelevantDrop:
    def __init__(self, relevant_drop_tuple):
        self.team_id = relevant_drop_tuple[0]
        self.player_id = relevant_drop_tuple[1]
        self.tile_id = relevant_drop_tuple[2]
        self.tile_name = relevant_drop_tuple[3]
        self.drop_name = relevant_drop_tuple[4]
        self.player_name = relevant_drop_tuple[5]
        self.relevant_drops_pk = relevant_drop_tuple[6]