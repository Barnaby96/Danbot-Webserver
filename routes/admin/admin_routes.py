import os
from functools import wraps

from flask import request, render_template, Blueprint, flash, redirect, url_for, abort, current_app, send_file
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from routes import dink
from utils import database, db_entities, wom
from utils.database import get_player_names, get_tile_names, get_tiles
from utils.spoofed_jsons.spoof_chat import spoof_chat
from utils.spoofed_jsons.spoof_drop import award_drop_json
from utils.spoofed_jsons.spoof_kc import kc_spoof_json
from utils.spoofed_jsons.spoof_pet import spoof_pet

admin_routes = Blueprint("admin_routes", __name__)
def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)  # Forbidden
        return f(*args, **kwargs)
    return decorated_function

@admin_routes.route('/', methods=['GET'])
@admin_required
def home():
    return render_template('admin_templates/admin_home.html')

@admin_routes.route('/dink_audit', methods=['GET'])
@admin_required
def dink_audit():
    audit_rows = database.get_recent_dink_auth_failures(
        limit=100
    )

    audit_entries = [
        {
            'audit_id': row[0],
            'failure_reason': row[1],
            'claimed_player_name': row[2],
            'claimed_dink_account_hash': row[3],
            'claimed_event_type': row[4],
            'request_format': row[5],
            'source_ip': row[6],
            'user_agent': row[7],
            'received_at': row[8]
        }
        for row in audit_rows
    ]

    return render_template(
        'admin_templates/dink_audit.html',
        audit_entries=audit_entries
    )


@admin_routes.route(
    '/dink_event/<int:event_id>/screenshot',
    methods=['GET']
)
@admin_required
def dink_event_screenshot(event_id):
    event = database.get_dink_event_by_id(
        event_id
    )

    if event is None or not event[8]:
        abort(404)

    screenshot_path = event[8]

    evidence_directory = os.path.realpath(
        os.path.join(
            current_app.root_path,
            'uploads',
            'dink_evidence'
        )
    )

    absolute_path = os.path.realpath(
        os.path.join(
            current_app.root_path,
            screenshot_path
        )
    )

    try:
        common_path = os.path.commonpath(
            [
                evidence_directory,
                absolute_path
            ]
        )
    except ValueError:
        abort(404)

    if common_path != evidence_directory:
        abort(404)

    filename = os.path.basename(
        absolute_path
    )

    filename_root, extension = os.path.splitext(
        filename
    )

    if filename_root != f'dink_event_{event_id}':
        abort(404)

    if extension.lower() not in {
        '.png',
        '.jpg',
        '.jpeg',
        '.webp'
    }:
        abort(404)

    if not os.path.isfile(absolute_path):
        abort(404)

    return send_file(
        absolute_path
    )

@admin_routes.route(
    '/dink_identities',
    methods=['GET', 'POST']
)
@admin_required
def dink_identities():
    if request.method == 'POST':
        action = request.form.get(
            'action',
            ''
        ).strip()

        if action != 'manual_link':
            flash(
                'Unknown Dink identity action.',
                'danger'
            )
            return redirect(
                url_for('admin_routes.dink_identities')
            )

        dink_account_hash = request.form.get(
            'dink_account_hash',
            ''
        ).strip()

        player_id_value = request.form.get(
            'player_id',
            ''
        ).strip()

        if not dink_account_hash:
            flash(
                'A Dink account hash is required.',
                'danger'
            )
            return redirect(
                url_for('admin_routes.dink_identities')
            )

        try:
            player_id = int(player_id_value)

            if player_id <= 0:
                raise ValueError

        except (TypeError, ValueError):
            flash(
                'Please select a valid DanBot player.',
                'danger'
            )
            return redirect(
                url_for('admin_routes.dink_identities')
            )

        result = database.manually_link_dink_identity(
            dink_account_hash,
            player_id
        )

        if result['status'] == 'LINKED':
            player = database.get_player_by_id(
                result['player_id']
            )

            player_name = (
                player[1]
                if player is not None
                else f"Player {result['player_id']}"
            )

            flash(
                f'Dink identity linked to {player_name}. '
                'Historical pending events were not processed.',
                'success'
            )

        elif result['status'] == 'IDENTITY_NOT_FOUND':
            flash(
                'That Dink identity no longer exists.',
                'danger'
            )

        elif result['status'] == 'PLAYER_NOT_FOUND':
            flash(
                'The selected DanBot player no longer exists.',
                'danger'
            )

        elif result['status'] == 'IDENTITY_ALREADY_LINKED':
            flash(
                'That Dink identity is already linked to '
                'a different player.',
                'danger'
            )

        elif result['status'] == 'PLAYER_ALREADY_LINKED':
            flash(
                'That player is already linked to Dink hash '
                f"{result['existing_linked_hash']}.",
                'danger'
            )

        else:
            flash(
                'The Dink identity could not be linked.',
                'danger'
            )

        return redirect(
            url_for('admin_routes.dink_identities')
        )

    identity_rows = database.get_dink_identity_review_rows()

    identity_entries = []

    for row in identity_rows:
        stored_status = row[2]
        observations = row[9]
        conflicting_rsns = row[10] or []
        matching_player_id = row[11]
        existing_linked_hash = row[14]

        display_status = stored_status
        review_reason = None

        if stored_status == 'LINKED':
            review_reason = 'Verified and linked'

        elif stored_status == 'CONFLICT':
            if conflicting_rsns:
                review_reason = (
                    'Hash seen with conflicting RSNs'
                )
            elif existing_linked_hash:
                review_reason = (
                    'Player already linked to another '
                    'Dink account'
                )
            else:
                review_reason = (
                    'Identity conflict requires review'
                )

        elif stored_status == 'PENDING':
            if (
                observations >= 3
                and matching_player_id is None
            ):
                display_status = 'PLAYER_NOT_FOUND'
                review_reason = (
                    'Three or more observations but no '
                    'matching DanBot player'
                )
            elif observations < 3:
                review_reason = (
                    f'Awaiting verification '
                    f'({observations}/3 observations)'
                )
            else:
                review_reason = (
                    'Identity still pending review'
                )

        identity_entries.append(
            {
                'dink_account_hash': row[0],
                'observed_rsn': row[1],
                'stored_status': stored_status,
                'display_status': display_status,
                'player_id': row[3],
                'linked_player_name': row[4],
                'linked_team_name': row[5],
                'first_seen': row[6],
                'last_seen': row[7],
                'linked_at': row[8],
                'observations': observations,
                'conflicting_rsns': conflicting_rsns,
                'matching_player_id': matching_player_id,
                'matching_player_name': row[12],
                'matching_team_name': row[13],
                'existing_linked_hash': existing_linked_hash,
                'review_reason': review_reason
            }
        )

    players_by_team = database.get_players_by_team()

    return render_template(
        'admin_templates/dink_identities.html',
        identity_entries=identity_entries,
        players_by_team=players_by_team
    )


@admin_routes.route(
    '/dink_events',
    methods=['GET', 'POST']
)
@admin_required
def dink_events():
    if request.method == 'POST':
        action = request.form.get(
            'action',
            ''
        ).strip()

        event_id_value = request.form.get(
            'event_id',
            ''
        ).strip()

        try:
            event_id = int(event_id_value)

            if event_id <= 0:
                raise ValueError

        except (TypeError, ValueError):
            flash(
                'Please select a valid Dink event.',
                'danger'
            )
            return redirect(
                url_for('admin_routes.dink_events')
            )

        if action == 'reject_event':
            result = database.reject_pending_dink_event(
                event_id
            )

            if result['status'] == 'REJECTED':
                flash(
                    f'Dink event #{event_id} was rejected.',
                    'success'
                )

            elif result['status'] == 'EVENT_NOT_FOUND':
                flash(
                    'That Dink event no longer exists.',
                    'danger'
                )

            elif result['status'] == 'DUPLICATE_EVENT':
                flash(
                    'Duplicate Dink events cannot be '
                    'reviewed manually.',
                    'danger'
                )

            elif result['status'] == 'INVALID_STATUS':
                flash(
                    f'Dink event #{event_id} can no longer '
                    f'be rejected because its status is '
                    f"{result['current_status']}.",
                    'danger'
                )

            else:
                flash(
                    'The Dink event could not be rejected.',
                    'danger'
                )

            return redirect(
                url_for('admin_routes.dink_events')
            )

        if action == 'accept_event':
            event = database.get_dink_event_by_id(
                event_id
            )

            if event is None:
                flash(
                    'That Dink event no longer exists.',
                    'danger'
                )
                return redirect(
                    url_for('admin_routes.dink_events')
                )

            if event[2] is not None:
                flash(
                    'Duplicate Dink events cannot be '
                    'reviewed manually.',
                    'danger'
                )
                return redirect(
                    url_for('admin_routes.dink_events')
                )

            if event[10] != 'PENDING_IDENTITY':
                flash(
                    f'Dink event #{event_id} can no longer '
                    f'be accepted because its status is '
                    f'{event[10]}.',
                    'danger'
                )
                return redirect(
                    url_for('admin_routes.dink_events')
                )

            identity = database.get_dink_identity_by_hash(
                event[3]
            )

            if (
                identity is None
                or identity[3] != 'LINKED'
                or identity[1] is None
            ):
                flash(
                    'This Dink event cannot be accepted '
                    'until its identity is linked.',
                    'danger'
                )
                return redirect(
                    url_for('admin_routes.dink_events')
                )

            try:
                event_progress = dink.get_dink_event_progress(
                    event[7]
                )

                result = database.process_dink_event_progress(
                    event_id=event_id,
                    player_id=identity[1],
                    event_progress=event_progress
                )

            except ValueError as error:
                flash(
                    str(error),
                    'danger'
                )
                return redirect(
                    url_for('admin_routes.dink_events')
                )

            if result['status'] == 'IGNORED':
                dink.cleanup_ignored_dink_event(
                    event_id
                )

                flash(
                    f'Dink event #{event_id} was accepted '
                    'but did not match any active bingo '
                    'progress.',
                    'info'
                )

            else:
                flash(
                    f'Dink event #{event_id} was accepted '
                    'and processed.',
                    'success'
                )

            return redirect(
                url_for('admin_routes.dink_events')
            )

        flash(
            'Unknown Dink event review action.',
            'danger'
        )

        return redirect(
            url_for('admin_routes.dink_events')
        )

    event_rows = (
        database.get_pending_dink_event_review_rows()
    )

    event_entries = []

    for row in event_rows:
        claimed_rsn = row[2]
        observed_rsn = row[8]

        rsn_mismatch = (
            isinstance(claimed_rsn, str)
            and isinstance(observed_rsn, str)
            and claimed_rsn.lower()
                != observed_rsn.lower()
        )

        event_entries.append(
            {
                'event_id': row[0],
                'dink_account_hash': row[1],
                'claimed_rsn': claimed_rsn,
                'event_type': row[3],
                'raw_payload': row[4],
                'screenshot_path': row[5],
                'received_at': row[6],
                'identity_status': row[7],
                'observed_rsn': observed_rsn,
                'linked_player_id': row[9],
                'linked_player_name': row[10],
                'linked_team_name': row[11],
                'rsn_mismatch': rsn_mismatch,
                'identity_ready': (
                    row[7] == 'LINKED'
                    and row[9] is not None
                )
            }
        )

    return render_template(
        'admin_templates/dink_events.html',
        event_entries=event_entries
    )

@admin_routes.route('/bingo_setup', methods=['GET', 'POST'])
@admin_required
def bingo_setup():
    competition_id = database.get_wom_competition_id()
    competition = None
    teams = {}
    wom_player_ids = {}
    participant_count = 0
    conflicts = []

    if request.method == 'POST':
        competition_id = request.form.get(
            'competition_id',
            ''
        ).strip()

        action = request.form.get('action', 'preview')

        try:
            competition = wom.get_competition_details(
                competition_id
            )
        except wom.WiseOldManError as error:
            flash(str(error), 'danger')
            return render_template(
                'admin_templates/bingo_setup.html',
                competition_id=competition_id,
                competition=None,
                teams={},
                participant_count=0,
                conflicts=[]
            )

        if competition.get('type') != 'team':
            flash(
                'The selected Wise Old Man competition is not '
                'a team competition.',
                'danger'
            )
            return render_template(
                'admin_templates/bingo_setup.html',
                competition_id=competition_id,
                competition=None,
                teams={},
                participant_count=0,
                conflicts=[]
            )

        participations = competition.get(
            'participations'
        ) or []

        for participation in participations:
            team_name = str(
                participation.get('teamName') or ''
            ).strip()

            player = participation.get('player') or {}

            player_name = str(
                player.get('displayName')
                or player.get('username')
                or ''
            ).strip()

            wom_player_id = participation.get('playerId')

            if wom_player_id is None:
                wom_player_id = player.get('id')

            if not team_name or not player_name:
                continue

            teams.setdefault(
                team_name,
                []
            ).append(player_name)

            if wom_player_id is not None:
                wom_player_ids[player_name.lower()] = int(
                    wom_player_id
                )

            participant_count += 1

        if participant_count == 0:
            flash(
                'No valid team participants were found in '
                'this competition.',
                'danger'
            )
            competition = None

        elif action == 'import':
            result = database.import_wom_competition(
                competition_id,
                teams,
                wom_player_ids
            )

            if not result['imported']:
                conflicts = result['conflicts']

                flash(
                    'The competition could not be imported '
                    'because some existing players are assigned '
                    'to different teams.',
                    'danger'
                )
            else:
                flash(
                    (
                        'Competition imported successfully. '
                        f"{result['teams_created']} teams created, "
                        f"{result['players_created']} players created "
                        f"and {result['players_reused']} existing "
                        'players reused.'
                    ),
                    'success'
                )

    return render_template(
        'admin_templates/bingo_setup.html',
        competition_id=competition_id,
        competition=competition,
        teams=teams,
        participant_count=participant_count,
        conflicts=conflicts
    )


@admin_routes.route('/submit_a_tile', methods=['GET', 'POST'])
@admin_required
def submit_a_tile():
    tile_types = {}
    tile_triggers = {}
    tiles = get_tiles()  # Adjusted to your function to get all tiles
    for tile in tiles:
        tile = db_entities.Tile(tile)
        tile_triggers[tile.tile_name] = []
        tile_types[tile.tile_name] = tile.tile_type
        if tile.tile_type != 'PET':
            for x in tile.tile_triggers.split(','):
                for trigger in x.split('/'):
                    tile_triggers[tile.tile_name].append(trigger.strip())

    if request.method == 'GET':
        return render_template('admin_templates/submit_a_tile.html', player_names=get_player_names(),
                               tile_names=get_tile_names(), tile_triggers=tile_triggers, tile_types=tile_types)

    if request.method == 'POST':
        player_names = get_player_names()
        tile_names = get_tile_names()

        # Handle the image file upload
        tile_type = tile_types[request.form['tile_name']]
        image_file = request.files.get('image')
        if tile_type == 'DROP' or tile_type == 'SET':
            json = award_drop_json(
                request.form['ign'],
                request.form['event_to_trigger'],
                int(request.form['value']),
                int(request.form['quantity'])
            )
            # Pass the image path to your parsing function or handle it accordingly
            dink.parse_loot(json, image_file)

        elif tile_type == 'KILLCOUNT':
            json = kc_spoof_json(
                request.form['ign'],
                request.form['event_to_trigger'],
                int(request.form['quantity'])
            )

            dink.parse_kill_count(json, image_file)

        elif tile_type == 'PET':
            json = spoof_pet(
                request.form['ign'],
                request.form['event_to_trigger']
            )

            dink.parse_pet(json, image_file)

        elif tile_type == 'CHAT':
            json = spoof_chat(
                request.form['ign'],
                request.form['event_to_trigger']
            )

            dink.parse_chat(json, image_file)

        elif tile_type == 'NICHE':
            flash("I'm still deciding how to deal with niche tile submission")
            return render_template('admin_templates/submit_a_tile.html', player_names=player_names,
                                   tile_names=tile_names, tile_triggers=tile_triggers, tile_types=tile_types)

        flash("Data submitted! Check the relevant Discord channel and make sure it shows up.")
        return render_template('admin_templates/submit_a_tile.html', player_names=player_names,
                               tile_names=tile_names, tile_triggers=tile_triggers, tile_types=tile_types)

@admin_routes.route('/reset_database', methods=['GET', 'POST'])
@admin_required
def reset_database():
    if not current_user.is_admin:
        flash("You do not have permission to access this page.", "danger")
        return redirect(url_for('home'))
    if request.method == 'POST':
        database.reset_tables()
        flash("Database reset successfully.")
    return render_template('admin_templates/reset_database.html')


@admin_routes.route('/start_tracking', methods=['GET', 'POST'])
@admin_required
def start_tracking():
    if not current_user.is_admin:
        flash("You do not have permission to access this page.", "danger")
        return redirect(url_for('home'))
    if request.method == 'POST':
        flash("Now tracking user data")
    return render_template('admin_templates/start_tracking.html')


@admin_routes.route('/stop_tracking', methods=['GET', 'POST'])
@admin_required
def stop_tracking():
    if not current_user.is_admin:
        flash("You do not have permission to access this page.", "danger")
        return redirect(url_for('home'))
    if request.method == 'POST':
        flash("No longer tracking user data")
    return render_template('admin_templates/stop_tracking.html')

@admin_routes.route('/hide_board', methods=['GET', 'POST'])
@admin_required
def hide_board():
    if not current_user.is_admin:
        flash("You do not have permission to access this page.", "danger")
        return redirect(url_for('home'))
    if request.method == 'POST':
        flash("Board will now be hidden. Uploading tiles will not change the visibility")
    return render_template('admin_templates/hide_board.html')

@admin_routes.route('/show_board', methods=['GET', 'POST'])
@admin_required
def show_board():
    if not current_user.is_admin:
        flash("You do not have permission to access this page.", "danger")
        return redirect(url_for('home'))
    if request.method == 'POST':
        flash("Board is now being show. Uploading tiles will not change the visibility")
    return render_template('admin_templates/show_board.html')
