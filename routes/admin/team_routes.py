from flask import Flask, render_template, request, redirect, url_for, flash, Blueprint

from routes.admin.admin_routes import admin_required
from utils import db_entities
from utils.database import add_team, get_teams, get_team_by_id, remove_team, rename_team, add_team_points, \
    update_team_webhook, get_players_by_team_id, remove_player, get_drops_by_team_id, remove_drop, remove_drop_by_pk, \
    get_partial_completions_by_team_id, get_team_by_discord_role_id, set_team_discord_role_id

team_routes = Blueprint("team_routes", __name__)

@team_routes.route('/teams', methods=['GET'])
@admin_required
def team_list():
    teams = get_teams()
    return render_template('admin_templates/team_templates/team_list.html', teams=teams)

@team_routes.route('/teams/new', methods=['GET', 'POST'])
@admin_required
def create_team():
    if request.method == 'POST':
        team_name = request.form.get('team_name')
        team_webhook = request.form.get('team_webhook')

        add_team(team_name, 0, team_webhook)

        flash('Team created successfully!', 'success')
        return redirect(url_for('team_routes.team_list'))

    return render_template('admin_templates/team_templates/new_team_form.html')

@team_routes.route('/teams/edit/<int:team_id>', methods=['GET', 'POST'])
@admin_required
def edit_team(team_id):
    team = get_team_by_id(team_id)
    team = db_entities.Team(team)
    if request.method == 'POST':
        new_team_name = request.form.get('team_name')
        team_points = request.form.get('team_points', 0)
        team_webhook = request.form.get('team_webhook')
        discord_role_id = request.form.get(
            'discord_role_id',
            ''
        ).strip()

        if discord_role_id:
            try:
                discord_role_id = int(discord_role_id)
            except ValueError:
                flash(
                    'Discord Role ID must be a number.',
                    'danger'
                )
                return redirect(
                    url_for(
                        'team_routes.edit_team',
                        team_id=team_id
                    )
                )

            existing_team = get_team_by_discord_role_id(
                discord_role_id
            )

            if (
                existing_team is not None
                and existing_team[3] != team_id
            ):
                flash(
                    'That Discord role is already assigned '
                    'to another team.',
                    'danger'
                )
                return redirect(
                    url_for(
                        'team_routes.edit_team',
                        team_id=team_id
                    )
                )
        else:
            discord_role_id = None

        # Renaming team
        rename_team(team.team_name, new_team_name)

        # Updating team points (add additional points or set new value)
        add_team_points(team_id, float(team_points) - team.team_points)

        # update webhook
        update_team_webhook(team_id, team_webhook)
        set_team_discord_role_id(
            team_id,
            discord_role_id
        )

        flash('Team updated successfully!', 'success')
        return redirect(url_for('team_routes.team_list'))

    return render_template('admin_templates/team_templates/edit_team.html', team=team)

@team_routes.route('/teams/delete/<int:team_id>', methods=['POST'])
@admin_required
def delete_team(team_id):
    remove_team(team_id)
    flash('Team deleted successfully!', 'success')
    return redirect(url_for('team_routes.team_list'))
