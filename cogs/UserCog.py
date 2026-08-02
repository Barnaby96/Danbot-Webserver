import os
import urllib
from collections import defaultdict

import discord
from discord.ext import commands

from utils import bingo, database, db_entities
from utils.autocomplete import player_names, team_names, tile_names, fuzzy_autocomplete

from utils.wom import WiseOldManError, get_group_member

ftext = "\u001b["

fnormal = "0;"
fbolt = "1;"
funderline = "4;"

fred = "31m"
fgreen = "32m"
fyellow = "33m"
fblue = "34m"
fwhite = "37m"
fend = ftext + "0m"

import os

def setup_names():
    folder_path = 'static/images/setups'
    folder_names = []

    for item_name in os.listdir(folder_path):
        item_path = os.path.join(folder_path, item_name)
        if os.path.isdir(item_path):
            folder_names.append(item_name)

    return folder_names



class UserCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @discord.slash_command(
        name="register",
        description="Link your Discord account to your OSRS account"
    )
    async def register(
        self,
        ctx: discord.ApplicationContext,
        rsn: discord.Option(str, "Your Old School RuneScape name")
    ):
        await ctx.defer(ephemeral=True)

        existing_link = database.get_player_by_discord_user_id(ctx.author.id)
        if existing_link is not None:
            player = db_entities.Player(existing_link)
            await ctx.respond(
                f"Your Discord account is already linked to "
                f"**{player.player_name}**.",
                ephemeral=True
            )
            return

        matched_teams = []

        for role in ctx.author.roles:
            team_data = database.get_team_by_discord_role_id(role.id)

            if team_data is not None:
                matched_teams.append(db_entities.Team(team_data))

        if len(matched_teams) == 0:
            await ctx.respond(
                "You do not have a recognised bingo team role.",
                ephemeral=True
            )
            return

        if len(matched_teams) > 1:
            await ctx.respond(
                "You have more than one bingo team role. "
                "Please ask an administrator to correct this.",
                ephemeral=True
            )
            return

        team = matched_teams[0]

        try:
            wom_player = get_group_member(rsn)
        except WiseOldManError as error:
            await ctx.respond(str(error), ephemeral=True)
            return

        if wom_player is None:
            await ctx.respond(
                f"**{rsn}** was not found in the configured "
                f"Wise Old Man group.",
                ephemeral=True
            )
            return

        display_name = wom_player["displayName"]
        player_data = database.get_player_by_name(display_name)

        if player_data is None:
            database.add_player(
                display_name,
                0,
                0,
                0,
                team.team_id,
                0
            )
            player_data = database.get_player_by_name(display_name)

        player = db_entities.Player(player_data)

        if player.team_id != team.team_id:
            current_team = db_entities.Team(
                database.get_team_by_id(player.team_id)
            )

            await ctx.respond(
                f"**{display_name}** is currently assigned to "
                f"**{current_team.team_name}**, but your Discord role "
                f"is for **{team.team_name}**. Please contact an "
                f"administrator.",
                ephemeral=True
            )
            return

        if player.discord_user_id is not None:
            await ctx.respond(
                f"**{display_name}** is already linked to another "
                f"Discord account.",
                ephemeral=True
            )
            return

        database.link_player_to_discord(
            player.player_id,
            ctx.author.id
        )

        await ctx.respond(
            f"Registration complete. Your Discord account is now "
            f"linked to **{display_name}** on **{team.team_name}**.",
            ephemeral=True
        )
    @discord.slash_command(name="help", description="A list of all my cool commands!")
    async def help(self, ctx: discord.ApplicationContext):
        commands_info = {
            "help": "A list of all my cool commands!",
            "dink": "Use this command to get help setting up your dink plugin.",
            "player": "Get a bunch of data about a player in the bingo.",
            "team": "Get a bunch of data about a team in the bingo.",
            "progress": "Check your progress on a specific tile.",
            "board": "Get a list of tiles you've already completed.",
            "leaderboard": "Show the current standings amongst teams and players."
        }

        response = "**Here are all my available commands:**\n\n"
        for command, description in commands_info.items():
            response += f"/{command} - {description}\n"

        await ctx.respond(response)

    @discord.slash_command(name="dink", description="Use this command to get help setting up your dink plugin")
    async def dink(self, ctx:discord.ApplicationContext):
        await ctx.defer()
        server_ip = os.getenv('SERVER_IP')
        player_url = f"http://{server_ip}/tutorial/dink"
        await ctx.respond(player_url)

    @discord.slash_command(name="player", description="Get a bunch of data about a player in the bingo")
    async def player(self, ctx: discord.ApplicationContext,
                     player_name: discord.Option(str, "What is the username?", autocomplete=lambda ctx: fuzzy_autocomplete(ctx, player_names()))):
        await ctx.defer()
        server_ip = os.getenv('SERVER_IP')
        player_url = f"http://{server_ip}/user/player/{player_name.replace(' ', '%20')}"
        await ctx.respond(player_url)

    @discord.slash_command(name="team", description="Get a bunch of data about a team in the bingo")
    async def team(self, ctx: discord.ApplicationContext,
                   team_name: discord.Option(str, "What is the team name?", autocomplete=lambda ctx: fuzzy_autocomplete(ctx, team_names()))):
        await ctx.defer()
        server_ip = os.getenv('SERVER_IP')
        team_url = f"http://{server_ip}/user/team/{team_name.replace(' ', '%20')}"
        await ctx.respond(team_url)


    @discord.slash_command(name="gear", description="View our catalog of gear setups for any content and budget")
    async def gear(self, ctx: discord.ApplicationContext,
                   setup: discord.Option(str, "What setup are you looking for?",
                                         autocomplete=lambda ctx: fuzzy_autocomplete(ctx, setup_names())),
                   budget: discord.Option(str, "Max or budget gear?",
                                          autocomplete=lambda ctx: fuzzy_autocomplete(ctx, ["budget", "max"]), default=None)):
        await ctx.defer()
        if budget is None:
            await ctx.respond(f""
                              f"# {setup.upper()}\n"
                              f"### BUDGET {setup.upper()}\n"
                              f"https://danbot.up.railway.app/static/images/setups/{setup}/budget.png\n"
                              f"### MAX {setup.upper()}\n"
                              f"https://danbot.up.railway.app/static/images/setups/{setup}/max.png\n")
        elif budget.lower() == "max":
            await ctx.respond(f"# MAX {setup.upper()}\n"
                              f"https://danbot.up.railway.app/static/images/setups/{setup}/max.png\n")
        elif budget.lower() == "budget":
            await ctx.respond(f"# BUDGET {setup.upper()}\n"
                              f"https://danbot.up.railway.app/static/images/setups/{setup}/budget.png\n")
        return

    @discord.slash_command(name="progress", description="Check your progress on a specific tile")
    async def progress(self, ctx:discord.ApplicationContext,
                       team_name: discord.Option(str, "What is your team name?", autocomplete=lambda ctx: fuzzy_autocomplete(ctx, team_names())),
                       tile_name: discord.Option(str, "What tile are you checking?", autocomplete=lambda ctx: fuzzy_autocomplete(ctx, tile_names()))):
        await ctx.defer()
        team = db_entities.Team(database.get_team_by_name(team_name))
        tile = db_entities.Tile(database.get_tile_by_name(tile_name))
        progress = bingo.check_progress(tile, team)
        if progress is None:
            await ctx.respond(f"You have fully completed {tile.tile_name}!")
        else:
            await ctx.respond(progress)

    @discord.slash_command(name="board", description="Get a list of tiles you've already completed")
    async def board(self, ctx:discord.ApplicationContext,
                    team_name: discord.Option(str, "What is your team name?", autocomplete=lambda ctx: fuzzy_autocomplete(ctx, team_names())),
                    board_type: discord.Option(str, "What kind of board would you like to see?", autocomplete=discord.utils.basic_autocomplete(["All Tiles","Completed Tiles","Incomplete Tiles", "Partial Tiles"]))):
        await ctx.defer()
        response = f"## {board_type} for {team_name}\n"
        team = db_entities.Team(database.get_team_by_name(team_name))
        tiles = database.get_tiles()
        completed_tiles = database.get_completed_tiles()
        complete_tile_dict = defaultdict(int)
        for tile in completed_tiles:
            tile = db_entities.CompletedTile(tile)
            if tile.team_id == team.team_id:
                complete_tile_dict[tile.tile_id] = complete_tile_dict[tile.tile_id] + 1

        if board_type == "All Tiles":
            for tile in tiles:
                tile = db_entities.Tile(tile)
                if complete_tile_dict != 0:
                    response = response + f"{tile.tile_name}: "
                    for i in range(min(complete_tile_dict[tile.tile_id], tile.tile_repetition)):
                        response = response + ":white_check_mark:"
                    for i in range(0, tile.tile_repetition - complete_tile_dict[tile.tile_id]):
                        response = response + ":x:"
                    response = response + "\n"
        elif board_type == "Completed Tiles":
            for tile in tiles:
                tile = db_entities.Tile(tile)
                if complete_tile_dict[tile.tile_id] > 0:
                    response = response + f"{tile.tile_name}: "
                    for i in range(min(complete_tile_dict[tile.tile_id], tile.tile_repetition)):
                        response = response + ":white_check_mark:"
                    for i in range(0, tile.tile_repetition - complete_tile_dict[tile.tile_id]):
                        response = response + ":x:"
        elif board_type == "Incomplete Tiles":
            for tile in tiles:
                tile = db_entities.Tile(tile)
                if complete_tile_dict[tile.tile_id] == 0:
                    response = response + f"{tile.tile_name}: "
                    for i in range(0, tile.tile_repetition - complete_tile_dict[tile.tile_id]):
                        response = response + ":x:"
                    response = response + "\n"
        elif board_type == "Partial Tiles":
            for tile in tiles:
                tile = db_entities.Tile(tile)
                progress = bingo.check_progress(tile, team)
                if progress is not None:
                    response = response + progress

        await ctx.respond(response)

    @discord.slash_command(name="leaderboard", description="Show the current standings amongst teams and players")
    async def leaderboard(self, ctx: discord.ApplicationContext):
        await ctx.defer()
        server_ip = os.getenv('SERVER_IP')
        leaderboard_url = f"http://{server_ip}/user/leaderboard"
        await ctx.respond(leaderboard_url)