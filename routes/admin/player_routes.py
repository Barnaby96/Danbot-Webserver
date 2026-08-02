import os

from flask import Flask, render_template, request, redirect, url_for, flash, Blueprint

from routes.admin.admin_routes import admin_required
from utils import db_entities
from utils.database import add_player, get_players, get_player_by_id, remove_player, rename_player, \
    get_players_by_team_id, update_player, change_player_team, get_team_by_name, get_teams, get_players_by_team, \
    get_team_by_id
import requests



player_routes = Blueprint("player_management", __name__)

@player_routes.route('/players', methods=['GET'])
@admin_required
def player_list():
    players_by_team = get_players_by_team()
    return render_template('admin_templates/player_templates/player_list.html', players_by_team=players_by_team)


API_KEY = os.getenv('WOM_KEY')
DISCORD_NAME = os.getenv(
    "WOM_USER_AGENT",
    "DanBot Development"
)

@player_routes.route('/add_list/<int:team_id>', methods=['GET', 'POST'])
@admin_required
def add_player_list(team_id):
    team = get_team_by_id(team_id)
    team = db_entities.Team(team)
    team_name = team.team_name
    successful = True
    if request.method == 'POST':
        players_to_add = []
        for player in request.form.get('player_names').split('\n'):
            player = player.strip().replace('\r','')
            headers = {
                'x-api-key': API_KEY,
                'User-Agent': DISCORD_NAME
            }
            response = requests.get(f'https://api.wiseoldman.net/v2/players/{player.strip().replace("-", "%20")}',
                                    headers)

            if response.status_code == 200:
                data = response.json()
                foundName = data['displayName']
                if foundName.lower() != player.lower():
                    flash(f'Warning! {player} does not exist but instead found {foundName}. Adding {foundName} instead. ')
                    player = foundName

                players_to_add.append(player)
            elif response.status_code == 404:
                response_suggestion = requests.get(f"https://api.wiseoldman.net/v2/players/search?username={player.strip().replace('-', '%20')}&limit=1")
                response_data = response_suggestion.json()

                if response_data and len(response_data) > 0:
                    suggested_name = response_data[0]["displayName"]
                    flash(
                        f'The given RSN {player} does not exist and was not added to the team. Did you mean {suggested_name} instead?',
                        'danger')
                else:
                    flash(f'The given RSN {player} does not exist and was not added to the team.', 'danger')

                successful = False
                continue
            else:
                flash('We are limited to checking 100 usernames per minute. Please wait before trying again (no players were added)', 'danger')
                return render_template('admin_templates/player_templates/new_player_list.html', team_name=team_name,
                                       team_id=team_id)

        for player in players_to_add:
            add_player(player, 0, 0, 0, team_id, 0)

        if successful:
            flash('Added all players!')
            return redirect(url_for('team_routes.team_list'))
        else:
            return render_template('admin_templates/player_templates/new_player_list.html', team_name=team_name, team_id=team_id)

    return render_template('admin_templates/player_templates/new_player_list.html', team_name=team_name, team_id=team_id)


@player_routes.route('/new', methods=['GET', 'POST'])
@admin_required
def create_player():
    teams = get_teams()  # Fetch all teams to get their names
    if request.method == 'POST':
        player = request.form.get('player_name')
        team_name = request.form.get('team_name')

        # Call the external API to search for the player
        headers = {
            'x-api-key': API_KEY,
            'User-Agent': DISCORD_NAME
        }
        response = requests.get(f'https://api.wiseoldman.net/v2/players/{player.strip().replace("-", "%20")}', headers)

        if response.status_code == 200:
            data = response.json()
            foundName = data['displayName']
            if foundName.lower() != player.lower():
                flash(f'Warning! {player} does not exist but instead found {foundName}. Adding {foundName} instead. ')
                player = foundName

            # Get team_id by team_name
            team = get_team_by_name(team_name)
            team_id = team[3]  # Assuming team_id is in the 4th position in the result

            add_player(player, 0, 0, 0, team_id, 0)

            flash('Player created successfully!', 'success')
            return redirect(url_for('player_management.player_list'))
        elif response.status_code == 404:
            response_suggestion = requests.get(
                f"https://api.wiseoldman.net/v2/players/search?username={player.strip().replace('-', '%20')}&limit=1")
            flash(
                f'The given RSN {player} does not exist and was not added to the team. Did you mean {response_suggestion.json()[0]["displayName"]} instead?',
                'danger')
        else:
            flash('Failed to connect to the Wise Old Man API. Please try again later.', 'danger')
            return redirect(url_for('player_management.create_player'))

    return render_template('admin_templates/player_templates/new_player_form.html', teams=teams)



@player_routes.route('/edit/<int:player_id>', methods=['GET', 'POST'])
@admin_required
def edit_player(player_id):
    player = get_player_by_id(player_id)
    teams = get_teams()  # Fetch all teams to get their names
    if request.method == 'POST':
        player_name = request.form.get('player_name')
        deaths = request.form.get('deaths', player[2])
        gp_gained = request.form.get('gp_gained', player[3])
        tiles_completed = request.form.get('tiles_completed', player[4])
        team_name = request.form.get('team_name')
        pet_count = request.form.get('pet_count', player[6])

        # Get team_id by team_name
        team = get_team_by_name(team_name)
        team_id = team[3]  # Assuming team_id is in the 4th position in the result

        update_player(player_id, player_name, deaths, gp_gained, tiles_completed, team_id, pet_count)

        flash('Player updated successfully!', 'success')
        return redirect(url_for('player_management.player_list'))

    return render_template('admin_templates/player_templates/edit_player.html', player=player, teams=teams)


@player_routes.route('/delete/<int:player_id>', methods=['GET','POST'])
@admin_required
def delete_player(player_id):
    remove_player(player_id)
    flash('Player deleted successfully!', 'success')
    return redirect(url_for('player_management.player_list'))
