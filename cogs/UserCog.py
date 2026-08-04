import os
import urllib
from collections import defaultdict

import discord
from discord.ext import commands

from utils import bingo, database, db_entities, scapify
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
            "help": (
                "Show this list of available commands."
            ),
            "register": (
                "Link your Discord account to your OSRS account."
            ),
            "dink": (
                "Get help setting up the Dink RuneLite plugin."
            ),
            "player": (
                "View a player's bingo statistics."
            ),
            "team": (
                "View a team's bingo statistics."
            ),
            "progress": (
                "Check your team's progress on a specific tile."
            ),
            "board": (
                "View your Discord-role team's board. "
                "Bingo Organisers may inspect another team."
            ),
            "leaderboard": (
                "Show the current team and player standings."
            ),
            "gear": (
                "View available gear setups."
            )
        }

        response = "**Here are all my available commands:**\n\n"
        for command, description in commands_info.items():
            response += f"/{command} - {description}\n"

        await ctx.respond(response)

    @discord.slash_command(
        name="dink",
        description="Get help setting up the Dink RuneLite plugin"
    )
    async def dink(
        self,
        ctx: discord.ApplicationContext
    ):
        await ctx.respond(
            "Dink tracking is not currently enabled on this "
            "development server.\n\n"
            "Once DanBot is publicly hosted, Bingo Organisers will "
            "provide the correct Dink import settings."
        )

    @discord.slash_command(
        name="player",
        description="View a player's bingo statistics"
    )
    async def player(
        self,
        ctx: discord.ApplicationContext,
        player_name: discord.Option(
            str,
            "Which player would you like to view?",
            autocomplete=lambda ctx: fuzzy_autocomplete(
                ctx,
                player_names()
            )
        )
    ):
        await ctx.defer()

        player_data = database.get_player_by_name(player_name)

        if player_data is None:
            await ctx.respond(
                f"Unable to find the player **{player_name}**."
            )
            return

        player = db_entities.Player(player_data)

        team_data = database.get_team_by_id(player.team_id)

        if team_data is None:
            team_name = "Unknown team"
        else:
            team_name = db_entities.Team(team_data).team_name

        tile_count = round(float(player.tiles_completed), 2)

        if tile_count.is_integer():
            tile_count = int(tile_count)

        partial_progress = 0

        for partial_data in (
            database.get_partial_completions_by_player_id(
                player.player_id
            )
        ):
            partial = db_entities.PartialCompletion(partial_data)
            partial_progress += float(
                partial.partial_completion
            )

        partial_progress = round(partial_progress, 2)

        drop_totals = defaultdict(
            lambda: {
                "quantity": 0,
                "value": 0
            }
        )

        for drop_data in database.get_drops_by_player_id(
            player.player_id
        ):
            drop = db_entities.Drop(drop_data)

            drop_totals[drop.drop_name]["quantity"] += (
                drop.drop_quantity
            )
            drop_totals[drop.drop_name]["value"] += (
                drop.drop_value * drop.drop_quantity
            )

        sorted_drops = sorted(
            drop_totals.items(),
            key=lambda item: item[1]["value"],
            reverse=True
        )

        drop_lines = []

        for drop_name, drop_details in sorted_drops[:10]:
            drop_lines.append(
                f"**{drop_name}** x"
                f"{drop_details['quantity']} - "
                f"{scapify.int_to_gp(drop_details['value'])}"
            )

        killcounts = []

        for killcount_data in (
            database.get_killcount_by_player_id(
                player.player_id
            )
        ):
            killcounts.append(
                db_entities.Killcount(killcount_data)
            )

        killcounts.sort(
            key=lambda killcount: killcount.kills,
            reverse=True
        )

        killcount_lines = [
            f"**{killcount.boss_name}:** {killcount.kills}"
            for killcount in killcounts[:10]
        ]

        relevant_drop_lines = []

        for relevant_drop_data in (
            database.get_relevant_drop_by_player_id(
                player.player_id
            )
        ):
            relevant_drop = db_entities.RelevantDrop(
                relevant_drop_data
            )

            relevant_drop_lines.append(
                f"**{relevant_drop.tile_name}:** "
                f"{relevant_drop.drop_name}"
            )

        embed = discord.Embed(
            title=player.player_name,
            description=f"Team: **{team_name}**"
        )

        embed.add_field(
            name="Bingo statistics",
            value=(
                f"Tiles completed: **{tile_count}**\n"
                f"Partial progress: **{partial_progress}**\n"
                f"GP gained: **"
                f"{scapify.int_to_gp(player.gp_gained)}**\n"
                f"Pets: **{player.pet_count}**\n"
                f"Deaths: **{player.deaths}**"
            ),
            inline=False
        )

        embed.add_field(
            name="Top drops",
            value=(
                "\n".join(drop_lines)
                if drop_lines
                else "No drops recorded."
            ),
            inline=False
        )

        embed.add_field(
            name="Kill counts",
            value=(
                "\n".join(killcount_lines)
                if killcount_lines
                else "No kill counts recorded."
            ),
            inline=False
        )

        if relevant_drop_lines:
            embed.add_field(
                name="Bingo-related drops",
                value="\n".join(relevant_drop_lines[:10]),
                inline=False
            )

        await ctx.respond(embed=embed)

    @discord.slash_command(
        name="team",
        description="View a team's bingo statistics"
    )
    async def team(
        self,
        ctx: discord.ApplicationContext,
        team_name: discord.Option(
            str,
            "Which team would you like to view?",
            autocomplete=lambda ctx: fuzzy_autocomplete(
                ctx,
                team_names()
            )
        )
    ):
        await ctx.defer()

        team_data = database.get_team_by_name(team_name)

        if team_data is None:
            await ctx.respond(
                f"Unable to find the team **{team_name}**."
            )
            return

        team = db_entities.Team(team_data)

        players = [
            db_entities.Player(player_data)
            for player_data in database.get_players_by_team_id(
                team.team_id
            )
        ]

        players.sort(
            key=lambda player: (
                player.tiles_completed,
                player.gp_gained
            ),
            reverse=True
        )

        total_gp = sum(player.gp_gained for player in players)
        total_deaths = sum(player.deaths for player in players)
        total_pets = sum(player.pet_count for player in players)
        total_tiles = sum(
            float(player.tiles_completed)
            for player in players
        )

        total_tiles = round(total_tiles, 2)

        if total_tiles.is_integer():
            total_tiles = int(total_tiles)

        partial_progress = 0

        for partial_data in (
            database.get_partial_completions_by_team_id(
                team.team_id
            )
        ):
            partial = db_entities.PartialCompletion(partial_data)
            partial_progress += float(
                partial.partial_completion
            )

        partial_progress = round(partial_progress, 2)

        player_lines = []

        for position, player in enumerate(players[:10], start=1):
            tile_count = round(
                float(player.tiles_completed),
                2
            )

            if tile_count.is_integer():
                tile_count = int(tile_count)

            tile_label = (
                "tile"
                if tile_count == 1
                else "tiles"
            )

            player_lines.append(
                f"**{position}. {player.player_name}** - "
                f"{tile_count} tiles | "
                f"{scapify.int_to_gp(player.gp_gained)}"
            )

        drop_totals = defaultdict(
            lambda: {
                "quantity": 0,
                "value": 0
            }
        )

        for drop_data in database.get_drops_by_team_id(
            team.team_id
        ):
            drop = db_entities.Drop(drop_data)

            drop_totals[drop.drop_name]["quantity"] += (
                drop.drop_quantity
            )
            drop_totals[drop.drop_name]["value"] += (
                drop.drop_value * drop.drop_quantity
            )

        sorted_drops = sorted(
            drop_totals.items(),
            key=lambda item: item[1]["value"],
            reverse=True
        )

        drop_lines = []

        for drop_name, drop_details in sorted_drops[:10]:
            drop_lines.append(
                f"**{drop_name}** x"
                f"{drop_details['quantity']} - "
                f"{scapify.int_to_gp(drop_details['value'])}"
            )

        killcount_totals = defaultdict(int)

        for killcount_data in database.get_killcount_by_team_id(
            team.team_id
        ):
            killcount = db_entities.Killcount(
                killcount_data
            )

            killcount_totals[killcount.boss_name] += (
                killcount.kills
            )

        sorted_killcounts = sorted(
            killcount_totals.items(),
            key=lambda item: item[1],
            reverse=True
        )

        killcount_lines = [
            f"**{boss_name}:** {kills}"
            for boss_name, kills in sorted_killcounts[:10]
        ]

        relevant_drop_lines = []

        for relevant_drop_data in (
            database.get_relevant_drop_by_team_id(
                team.team_id
            )
        ):
            relevant_drop = db_entities.RelevantDrop(
                relevant_drop_data
            )

            relevant_drop_lines.append(
                f"**{relevant_drop.tile_name}:** "
                f"{relevant_drop.drop_name} "
                f"({relevant_drop.player_name})"
            )

        team_points = round(float(team.team_points), 2)

        if team_points.is_integer():
            team_points = int(team_points)

        embed = discord.Embed(
            title=team.team_name,
            description=f"Bingo points: **{team_points}**"
        )

        embed.add_field(
            name="Team statistics",
            value=(
                f"Players: **{len(players)}**\n"
                f"Tiles completed: **{total_tiles}**\n"
                f"Partial progress: **{partial_progress}**\n"
                f"GP gained: **"
                f"{scapify.int_to_gp(total_gp)}**\n"
                f"Pets: **{total_pets}**\n"
                f"Deaths: **{total_deaths}**"
            ),
            inline=False
        )

        embed.add_field(
            name="Player standings",
            value=(
                "\n".join(player_lines)
                if player_lines
                else "No players are assigned to this team."
            ),
            inline=False
        )

        embed.add_field(
            name="Top drops",
            value=(
                "\n".join(drop_lines)
                if drop_lines
                else "No drops recorded."
            ),
            inline=False
        )

        embed.add_field(
            name="Kill counts",
            value=(
                "\n".join(killcount_lines)
                if killcount_lines
                else "No kill counts recorded."
            ),
            inline=False
        )

        if relevant_drop_lines:
            embed.add_field(
                name="Bingo-related drops",
                value="\n".join(relevant_drop_lines[:10]),
                inline=False
            )

        await ctx.respond(embed=embed)


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

    @discord.slash_command(
        name="progress",
        description="Check your team's progress on a specific tile"
    )
    async def progress(
        self,
        ctx: discord.ApplicationContext,
        tile_name: discord.Option(
            str,
            "Which tile are you checking?",
            autocomplete=lambda ctx: fuzzy_autocomplete(
                ctx,
                tile_names()
            )
        )
    ):
        await ctx.defer()

        player_data = database.get_player_by_discord_user_id(
            ctx.author.id
        )

        if player_data is None:
            await ctx.respond(
                "Your Discord account is not registered. "
                "Use `/register` first."
            )
            return

        player = db_entities.Player(player_data)

        team_data = database.get_team_by_id(player.team_id)
        if team_data is None:
            await ctx.respond(
                "Your registered bingo team could not be found. "
                "Please contact an administrator."
            )
            return

        team = db_entities.Team(team_data)

        tile_data = database.get_tile_by_name(tile_name)
        if tile_data is None:
            await ctx.respond(
                f"Unable to find the tile **{tile_name}**."
            )
            return

        tile = db_entities.Tile(tile_data)
        tile_progress = bingo.get_progress(
            team.team_id,
            tile.tile_id
        )

        await ctx.respond(tile_progress.status_text)

    @discord.slash_command(
        name="board",
        description="View your team's bingo board"
    )
    async def board(
        self,
        ctx: discord.ApplicationContext,
        board_type: discord.Option(
            str,
            "Which version of the board would you like?",
            autocomplete=discord.utils.basic_autocomplete(
                [
                    "All Tiles",
                    "Completed Tiles",
                    "Incomplete Tiles",
                    "Partial Tiles"
                ]
            )
        ),
        team_name: discord.Option(
            str,
            "Team to inspect — Bingo Organisers only",
            autocomplete=lambda ctx: fuzzy_autocomplete(
                ctx,
                team_names()
            ),
            default=None
        )
    ):

        await ctx.defer()

        player_data = database.get_player_by_discord_user_id(
            ctx.author.id
        )

        organiser_role_id = os.getenv(
            "BINGO_ORGANISER_ROLE_ID"
        )

        is_organiser = (
            organiser_role_id is not None
            and any(
                str(role.id) == organiser_role_id
                for role in ctx.author.roles
            )
        )

        if team_name is not None:
            if not is_organiser:
                await ctx.respond(
                    "Only Bingo Organisers can inspect another "
                    "team's board."
                )
                return

            team_data = database.get_team_by_name(team_name)

            if team_data is None:
                await ctx.respond(
                    f"Unable to find the team **{team_name}**."
                )
                return

            team = db_entities.Team(team_data)

        else:
            matched_teams = []

            for role in ctx.author.roles:
                team_data = (
                    database.get_team_by_discord_role_id(
                        role.id
                    )
                )

                if team_data is not None:
                    matched_teams.append(
                        db_entities.Team(team_data)
                    )

            if len(matched_teams) == 0:
                if is_organiser:
                    await ctx.respond(
                        "You do not have a bingo team role. "
                        "Choose a team using the optional "
                        "`team_name` field."
                    )
                else:
                    await ctx.respond(
                        "You do not have a recognised bingo "
                        "team role."
                    )
                return

            if len(matched_teams) > 1:
                await ctx.respond(
                    "You have more than one bingo team role. "
                    "Please ask an administrator to correct this."
                )
                return

            team = matched_teams[0]
        tiles = database.get_tiles()
        completed_tiles = database.get_completed_tiles()

        completion_counts = defaultdict(int)

        for completed_tile_data in completed_tiles:
            completed_tile = db_entities.CompletedTile(
                completed_tile_data
            )

            if completed_tile.team_id == team.team_id:
                completion_counts[completed_tile.tile_id] += 1

        lines = []

        for tile_data in tiles:
            tile = db_entities.Tile(tile_data)
            completions = completion_counts[tile.tile_id]

            if board_type == "All Tiles":
                completed_icons = (
                    ":white_check_mark:"
                    * min(completions, tile.tile_repetition)
                )
                incomplete_icons = (
                    ":x:"
                    * max(tile.tile_repetition - completions, 0)
                )

                lines.append(
                    f"**{tile.tile_name}:** "
                    f"{completed_icons}{incomplete_icons}"
                )

            elif board_type == "Completed Tiles":
                if completions > 0:
                    completed_icons = (
                        ":white_check_mark:"
                        * min(completions, tile.tile_repetition)
                    )
                    incomplete_icons = (
                        ":x:"
                        * max(tile.tile_repetition - completions, 0)
                    )

                    lines.append(
                        f"**{tile.tile_name}:** "
                        f"{completed_icons}{incomplete_icons}"
                    )

            elif board_type == "Incomplete Tiles":
                if completions == 0:
                    lines.append(
                        f"**{tile.tile_name}:** "
                        f"{':x:' * tile.tile_repetition}"
                    )

            elif board_type == "Partial Tiles":
                if completions >= tile.tile_repetition:
                    continue

                tile_progress = bingo.get_progress(
                    team.team_id,
                    tile.tile_id
                )

                if (
                    tile_progress is not None
                    and tile_progress.progress_value > 0
                ):
                    status_text = tile_progress.status_text

                    status_text = (
                        status_text
                        .replace("<p>", "")
                        .replace("</p>", "")
                        .replace("<ul>", "\n")
                        .replace("</ul>", "")
                        .replace("<li>", "• ")
                        .replace("</li>", "\n")
                        .strip()
                    )

                    lines.append(
                        f"**{tile.tile_name}**\n{status_text}"
                    )

        if not lines:
            lines.append(
                "There are no tiles matching this board view."
            )

        header = f"## {board_type} for {team.team_name}"
        messages = []
        current_message = header

        for line in lines:
            addition = f"\n{line}"

            if len(current_message) + len(addition) > 1900:
                messages.append(current_message)
                current_message = line
            else:
                current_message += addition

        messages.append(current_message)

        await ctx.respond(messages[0])

        for message in messages[1:]:
            await ctx.followup.send(message)

    @discord.slash_command(
        name="leaderboard",
        description="Show the current team and player standings"
    )
    async def leaderboard(
        self,
        ctx: discord.ApplicationContext
    ):
        await ctx.defer()

        players = [
            db_entities.Player(player_data)
            for player_data in database.get_players()
        ]

        teams = [
            db_entities.Team(team_data)
            for team_data in database.get_teams()
        ]

        team_gp = defaultdict(int)

        for player in players:
            team_gp[player.team_id] += player.gp_gained

        teams.sort(
            key=lambda team: (
                team.team_points,
                team_gp[team.team_id]
            ),
            reverse=True
        )

        players.sort(
            key=lambda player: (
                player.tiles_completed,
                player.gp_gained
            ),
            reverse=True
        )

        team_lines = []

        for position, team in enumerate(teams, start=1):
            team_points = round(float(team.team_points), 2)

            if team_points.is_integer():
                team_points = int(team_points)

            point_label = (
                "point"
                if team_points == 1
                else "points"
            )

            team_lines.append(
                f"**{position}. {team.team_name}** - "
                f"{team_points} {point_label} | "
                f"{scapify.int_to_gp(team_gp[team.team_id])}"
            )

        player_lines = []

        for position, player in enumerate(players, start=1):
            tile_count = round(float(player.tiles_completed), 2)

            if tile_count.is_integer():
                tile_count = int(tile_count)

            tile_label = (
                "tile"
                if tile_count == 1
                else "tiles"
            )

            player_lines.append(
                f"**{position}. {player.player_name}** - "
                f"{tile_count} {tile_label} | "
                f"{scapify.int_to_gp(player.gp_gained)}"
            )

        if not team_lines:
            team_lines.append("No teams have been created.")

        if not player_lines:
            player_lines.append("No players have been registered.")

        sections = [
            "## Team Standings\n" + "\n".join(team_lines),
            "## Player Standings\n" + "\n".join(player_lines)
        ]

        messages = []
        current_message = ""

        for section in sections:
            for line in section.splitlines():
                addition = line + "\n"

                if len(current_message) + len(addition) > 1900:
                    messages.append(current_message.rstrip())
                    current_message = addition
                else:
                    current_message += addition

        if current_message:
            messages.append(current_message.rstrip())

        await ctx.respond(messages[0])

        for message in messages[1:]:
            await ctx.followup.send(message)