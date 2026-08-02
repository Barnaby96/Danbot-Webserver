import sqlite3

from discord.ext import commands
from discord import default_permissions, guild_only

from routes import dink
from utils import scapify
from utils.spoofed_jsons import spoof_drop
from utils.autocomplete import *
from utils.send_webhook import send_webhook

class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.slash_command(
        name="set_team_role",
        description="Links a Discord role to a bingo team"
    )
    @default_permissions(manage_webhooks=True)
    @guild_only()
    async def set_team_role(
        self,
        ctx: discord.ApplicationContext,
        team_name: discord.Option(
            str,
            "Which bingo team is this role for?",
            autocomplete=lambda ctx: fuzzy_autocomplete(ctx, team_names())
        ),
        role: discord.Option(
            discord.Role,
            "Which Discord role belongs to this team?"
        )
    ):
        await ctx.defer()

        team_data = database.get_team_by_name(team_name)
        if team_data is None:
            await ctx.respond(f"Unable to find team: {team_name}")
            return

        team = db_entities.Team(team_data)

        existing_team_data = database.get_team_by_discord_role_id(role.id)
        if existing_team_data is not None:
            existing_team = db_entities.Team(existing_team_data)

            if existing_team.team_id != team.team_id:
                await ctx.respond(
                    f"{role.mention} is already linked to "
                    f"{existing_team.team_name}."
                )
                return

        database.set_team_discord_role_id(team.team_id, role.id)

        await ctx.respond(
            f"{role.mention} is now linked to {team.team_name}."
        )

    @discord.slash_command(name="add_player", description="Adds a player to the bingo")
    @default_permissions(manage_webhooks=True)
    @guild_only()
    async def add_player(self, ctx:discord.ApplicationContext,
                         player_name: discord.Option(str, "What is the players username?"),
                         team_name: discord.Option(str, "What team should this player be on?", autocomplete=lambda ctx: fuzzy_autocomplete(ctx, team_names()))):
        await ctx.defer()
        team = database.get_team_by_name(team_name)
        if team is not None:
            team = db_entities.Team(team)
        else:
            await ctx.respond(f"Team name {team_name} not found.")
            return

        database.add_player(player_name, 0, 0, 0, team.team_id, 0)
        await ctx.respond(f"{player_name} has been added to team {team.team_name}")

    @discord.slash_command(name="remove_player", description="Removes a player from the bingo")
    @default_permissions(manage_webhooks=True)
    @guild_only()
    async def remove_player(self, ctx:discord.ApplicationContext,
                            player_name: discord.Option(str, "What is the players username?", autocomplete=lambda ctx: fuzzy_autocomplete(ctx, player_names()))):
        await ctx.defer()
        player = database.get_player_by_name(player_name)
        if player is not None:
            player = db_entities.Player(player)
        else:
            await ctx.respond(f"{player_name} was not found.")
            return
        database.remove_player(player.player_id)
        await ctx.respond(f"Removed {player.player_name} from the bingo.")


    @discord.slash_command(name="change_player_team", description="Moves a player from one team to another")
    @default_permissions(manage_webhooks=True)
    @guild_only()
    async def change_player_team(self, ctx:discord.ApplicationContext,
                                 player_name: discord.Option(str, "What is the players username?", autocomplete=lambda ctx: fuzzy_autocomplete(ctx, player_names())),
                                 new_team_name: discord.Option(str, "What team should this player be on?", autocomplete=lambda ctx: fuzzy_autocomplete(ctx, team_names()))):
        await ctx.defer()
        player = database.get_player_by_name(player_name)
        if player is None:
            await ctx.respond(f"Unable to find player, {player_name}")
            return False
        player = db_entities.Player(player)

        new_team = database.get_team_by_name(new_team_name)
        if new_team is None:
            await ctx.respond(f"Unable to find team, {new_team_name}")
            return False
        team = db_entities.Team(new_team)

        database.change_player_team(player.player_id, team.team_id)
        await ctx.respond(f"Succesfully moved all data from {player.player_name} to {team.team_name}")

    @discord.slash_command(name="award_drop", description="Manually award a drop")
    @default_permissions(manage_webhooks=True)
    @guild_only()
    async def award_drop(self, ctx:discord.ApplicationContext,
                         player_name: discord.Option(str, "What is the username?", autocomplete=lambda ctx: fuzzy_autocomplete(ctx, player_names())),
                         drop_name: discord.Option(str, "What is the drop name?", autocomplete=lambda ctx: fuzzy_autocomplete(ctx, drop_names())),
                         quantity: discord.Option(int, "How many drops did they get?", default=1),
                         drop_value: discord.Option(int, "How much is each drop worth?", default=0)):
        await ctx.defer()

        player = database.get_player_by_name(player_name)
        if player is None:
            await ctx.respond(f"Unable to find player, {player_name}")
            return False
        player = db_entities.Player(player)

        json_data = spoof_drop.award_drop_json(player.player_name, drop_name, drop_value, quantity)
        result = dink.parse_loot(json_data, None)

        if result:
            await ctx.respond(f"Successfully awarded {player.player_name} with {quantity} x {drop_name} at {scapify.int_to_gp(drop_value)} each")
        else:
            await ctx.respond(f"Something went wrong. Check my console or contact Danbis before attempting again.")

    @discord.slash_command(name="add_team_points", description="Add points to a team")
    @default_permissions(manage_webhooks=True)
    @guild_only()
    async def add_team_points(self,
                              ctx:discord.ApplicationContext,
                              team_name: discord.Option(str, "What team are you awarding points to?", autocomplete=lambda ctx: fuzzy_autocomplete(ctx, team_names())),
                              points: discord.Option(int, "How many points would you like to award?")):
        await ctx.defer()
        team = database.get_team_by_name(team_name)
        if team is None:
            await ctx.respond(f"Unable to find team, {team_name}")
            return False
        team = db_entities.Team(team)
        database.add_team_points(team.team_id, points)
        await ctx.respond(f"Successfully awarded {team.team_name} {points} points!")

    @discord.slash_command(name="remove_team_points", description="Add points to a team")
    @default_permissions(manage_webhooks=True)
    @guild_only()
    async def remove_team_points(self,
                              ctx:discord.ApplicationContext,
                              team_name: discord.Option(str, "What team are you removing points from?", autocomplete=lambda ctx: fuzzy_autocomplete(ctx, team_names())),
                              points: discord.Option(int, "How many points would you like to remove?")):
        await ctx.defer()
        team = database.get_team_by_name(team_name)
        if team is None:
            await ctx.respond(f"Unable to find team, {team_name}")
            return False
        team = db_entities.Team(team)
        database.add_team_points(team.team_id, -points)
        await ctx.respond(f"Successfully removed {team.team_name} {points} points!")

    @discord.slash_command(name="add_tile_completion", description="Mark a tile as completed for a team")
    @default_permissions(manage_webhooks=True)
    @guild_only()
    async def add_tile_completion(self,
                                  ctx:discord.ApplicationContext,
                                  team_name: discord.Option(str, "What team is completing a tile?", autocomplete=lambda ctx: fuzzy_autocomplete(ctx, team_names())),
                                  tile_name: discord.Option(str, "What tile are they completing", autocomplete=lambda ctx: fuzzy_autocomplete(ctx, tile_names()))):
        await ctx.defer()
        team = database.get_team_by_name(team_name)
        if team is None:
            await ctx.respond(f"Unable to find team, {team_name}")
            return False
        team = db_entities.Team(team)
        tile = database.get_tile_by_name(tile_name)
        if tile is None:
            await ctx.respond(f"Unable to find tile, {tile_name}")
            return False
        tile = db_entities.Tile(tile)
        database.add_completed_tile(tile.tile_id, team.team_id)
        await ctx.respond(f"I've added a tile completion for {team.team_name} on tile {tile.tile_name}. "
                          f"NOTE: I did not add any points during this operation! Please use /add_team_points if required")

    @discord.slash_command(name="remove_tile_completion", description="Mark a tile as completed for a team")
    @default_permissions(manage_webhooks=True)
    @guild_only()
    async def remove_tile_completion(self,
                                  ctx:discord.ApplicationContext,
                                  team_name: discord.Option(str, "What team is completing a tile?", autocomplete=lambda ctx: fuzzy_autocomplete(ctx, team_names())),
                                  tile_name: discord.Option(str, "What tile are they completing", autocomplete=lambda ctx: fuzzy_autocomplete(ctx, tile_names()))):
        await ctx.defer()
        team = database.get_team_by_name(team_name)
        if team is None:
            await ctx.respond(f"Unable to find team, {team_name}")
            return False
        team = db_entities.Team(team)
        tile = database.get_tile_by_name(tile_name)
        if tile is None:
            await ctx.respond(f"Unable to find tile, {tile_name}")
            return False
        tile = db_entities.Tile(tile)
        database.remove_completed_tile(tile.tile_id, team.team_id)
        await ctx.respond(f"I've remove a tile completion for {team.team_name} on tile {tile.tile_name}."
                          f"NOTE: I did not remove any points during this operation! Please use /remove_team_points if required")


    @discord.slash_command(name="run_query", description="DANGER! IF YOU'RE NOT DANBIS OR DON'T KNOW WHAT YOUR DOING DON'T RUN THIS COMMAND")
    @default_permissions(manage_webhooks=True)
    @guild_only()
    async def run_query(self, ctx:discord.ApplicationContext,
                        query: discord.Option(str)):
        await ctx.defer()
        with database.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            await ctx.respond(f"Executed query: ```{query}```\nResponse data: ```{cursor.fetchall()}```")

    @discord.slash_command(name="remove_manual_progress", description="Remove tile progress from a tile")
    @default_permissions(manage_webhooks=True)
    @guild_only()
    async def remove_manual_progress(self,
                                     ctx: discord.ApplicationContext,
                                     player_name: discord.Option(str, "What is the players name?", autocomplete=lambda ctx: fuzzy_autocomplete(ctx, player_names())),
                                     tile_name: discord.Option(str, "What is the tile_name?", autocomplete=lambda ctx: fuzzy_autocomplete(ctx, tile_names())),
                                     progress: discord.Option(int, "What trigger value would you like to remove?")):
        await ctx.defer()

        tile = database.get_tile_by_name(tile_name)
        if tile is None:
            await ctx.respond(f"Unable to find tile, {tile_name}")
            return False
        tile = db_entities.Tile(tile)

        player = database.get_player_by_name(player_name)
        if player is None:
            await ctx.respond(f"Unable to find player, {player_name}")
            return False
        player = db_entities.Player(player)

        team = db_entities.Team(database.get_team_by_id(player.team_id))

        database.add_manual_progress(tile.tile_name, player.player_name, -progress)
        database.add_player_tile_completions(player.player_id, -progress / tile.tile_triggers_required)
        await ctx.respond(f"Successfully removed manual progress from {team.team_name} for tile {tile.tile_name}. I've also removed {progress/tile.tile_triggers_reuired} from {player.player_name}'s tile completions")

    @discord.slash_command(name="award_manual_progress", description="Add tile progress to a tile")
    @default_permissions(manage_webhooks=True)
    @guild_only()
    async def award_manual_progress(self,
                                    ctx: discord.ApplicationContext,
                                    player_name: discord.Option(str, "What is the players name?", autocomplete=lambda ctx: fuzzy_autocomplete(ctx, player_names())),
                                    tile_name: discord.Option(str, "What is the tile_name?", autocomplete=lambda ctx: fuzzy_autocomplete(ctx, tile_names())),
                                    progress: discord.Option(int, "What trigger value would you like to add?")):
        await ctx.defer()

        tile = database.get_tile_by_name(tile_name)
        if tile is None:
            await ctx.respond(f"Unable to find tile, {tile_name}")
            return False
        tile = db_entities.Tile(tile)

        player = database.get_player_by_name(player_name)
        if player is None:
            await ctx.respond(f"Unable to find player, {player_name}")
            return False
        player = db_entities.Player(player)
        team = db_entities.Team(database.get_team_by_id(player.team_id))

        tile_completions = len(database.get_completed_tiles_by_team_id_and_tile_id(player.team_id, tile.tile_id))
        if tile_completions >= tile.tile_repetition:
            response = f"This tile has already been completed {tile.tile_repetition} times. There is no point in awarding more progress."
            ctx.respond(response)
            return

        database.add_manual_progress(tile.tile_name, player.player_name, progress)

        database.add_player_partial_completions(player.player_id, team.team_id, tile.tile_id, progress / tile.tile_triggers_required)
        response = f"Successfully added {progress} manual progress/trigger weight to {tile.tile_name} for {player.player_name}'s team. Additionally I've given {player.player_name} {round(progress/tile.tile_triggers_required, 2)} partial completions"
        progress = database.get_manual_progress_by_tile_id_and_team_id(tile.tile_id, player.team_id)
        if progress >= (tile_completions + 1) * tile.tile_triggers_required:
            database.add_completed_tile(tile.tile_id, player.team_id)
            database.add_team_points(player.team_id, tile.tile_points)
            if int(progress % tile.tile_triggers_required) == tile.tile_triggers_required:
                progress = 0
            send_webhook(team.team_webhook, title=f"{tile.tile_name} completed!", description=f"You now have {tile_completions + 1} completions and are {int(progress % tile.tile_triggers_required)}/{tile.tile_triggers_required} from your next completion", color=65280, image=None)
            response = response + f"\nIt seems they have also completed this tile so I've awarded them {tile.tile_points} points and sent them a message letting them know! They now have {tile_completions + 1} completions for this tile"
            current_trigger_rewards = 0
            for partial_completion in database.get_partial_completions_by_team_id_and_tile_id(team.team_id,
                                                                                              tile.tile_id):
                partial_completion = db_entities.PartialCompletion(partial_completion)
                database.remove_partial_completion(partial_completion.partial_completion_pk)
                database.add_player_tile_completions(partial_completion.player_id,
                                                     min(partial_completion.partial_completion,
                                                         1 - current_trigger_rewards))
                if round(partial_completion.partial_completion, 2) > round(1 - current_trigger_rewards,
                                                                           2) and tile_completions + 1 < tile.tile_repetition:
                    database.add_player_partial_completions(player.player_id, team.team_id, tile.tile_id,
                                                            partial_completion.partial_completion - (1 - current_trigger_rewards))
                else:
                    current_trigger_rewards += partial_completion.partial_completion
        else:
            send_webhook(team.team_webhook, title=f"Request approved for {tile.tile_name}!", description=f"You are now {int(progress % tile.tile_triggers_required)}/{tile.tile_triggers_required} away from completing this tile", color=16776960, image=None)

        await ctx.respond(response)

    @discord.slash_command(name="rename_team", description="Rename a team")
    @default_permissions(manage_webhooks=True)
    @guild_only()
    async def rename_team(self,
                    ctx: discord.ApplicationContext,
                    old_team_name: discord.Option(str, "What is the old team name?", autocomplete=lambda ctx: fuzzy_autocomplete(ctx, team_names())),
                    new_team_name: discord.Option(str, "What is the new team name?")):
        await ctx.defer()

        team = database.get_team_by_name(old_team_name)

        if team is None:
            await ctx.respond(f"Unable to find team, {old_team_name}")
            return False

        database.rename_team(old_team_name, new_team_name)
        await ctx.respond(f"Updated {old_team_name}'s name to {new_team_name}")

    @discord.slash_command(name="rename_player", description="Rename a player")
    @default_permissions(manage_webhooks=True)
    @guild_only()
    async def rename_player(self,
                    ctx: discord.ApplicationContext,
                    old_player_name: discord.Option(str, "What is the old player name?", autocomplete=lambda ctx: fuzzy_autocomplete(ctx, player_names())),
                    new_player_name: discord.Option(str, "What is the new player name?")):
        await ctx.defer()

        player = database.get_player_by_name(old_player_name)
        if player is None:
            await ctx.respond(f"Unable to find player, {old_player_name}")
            return False

        database.rename_player(old_player_name, new_player_name)
        await ctx.respond(f"Updated {old_player_name}'s name to {new_player_name}")

    @discord.slash_command(name="rename_drop", description="Renames a drop if you input an incorrect trigger")
    @default_permissions(manage_webhooks=True)
    @guild_only()
    async def rename_drop(self,
                          ctx: discord.ApplicationContext,
                          old_drop_name: discord.Option(str, "What is the incorrect drop name?", autocomplete=lambda ctx: fuzzy_autocomplete(ctx, drop_names())),
                          new_drop_name: discord.Option(str, "What is the new drop name?")):
        await ctx.defer()

        tile = database.get_tile_by_drop(old_drop_name)
        if tile is None:
            await ctx.respond(f"Unable to find drop, {old_drop_name}")
            return False
        tile[4] = tile[4].replace(old_drop_name, new_drop_name)
        tile = db_entities.Tile(tile)

        database.update_drop_whitelist_name(old_drop_name, new_drop_name)
        database.update_tile_trigger(tile.tile_id, tile.tile_triggers)

    @discord.slash_command(name="replace_trigger", description="Replaces a trigger if you input the trigger incorrectly")
    @default_permissions(manage_webhooks=True)
    @guild_only()
    async def replace_trigger(self,
                          ctx: discord.ApplicationContext,
                          tile_name: discord.Option(str, "What is the tile name?", autocomplete=lambda ctx: fuzzy_autocomplete(ctx, tile_names())),
                          new_trigger: discord.Option(str, "What is the new trigger?")):
        await ctx.defer()

        tile = database.get_tile_by_name(tile_name)
        if tile is None:
            await ctx.respond(f"Unable to find tile, {tile_name}")
            return False
        tile[4] = new_trigger
        tile = db_entities.Tile(tile)

        database.remove_drop_whitelist_by_tile_id(tile.tile_id)
        database.update_tile_trigger(tile.tile_id, tile.tile_triggers)

        for i in new_trigger.split("/"):
            for item in i.split(","):
                if item.strip() == "":
                    continue
                database.add_drop_whitelist(item.strip(), tile.tile_id)