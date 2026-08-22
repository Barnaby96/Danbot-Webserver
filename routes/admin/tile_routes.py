from flask import Flask, render_template, request, redirect, url_for, flash, Blueprint

from routes.admin.admin_routes import admin_required
from utils.database import (
    remove_tile,
    get_tile_by_id,
    get_tile_conditions,
    add_tile_with_conditions,
    update_tile_with_conditions,
    get_tiles
)

tile_routes = Blueprint("tile_management", __name__)


@tile_routes.route('/tiles', methods=['GET'])
@admin_required
def tile_list():
    tiles = get_tiles()
    return render_template('admin_templates/tile_templates/tile_list.html', tiles=tiles)

@tile_routes.route('/tiles/new', methods=['GET', 'POST'])
@admin_required
def create_tile():
    if request.method == 'POST':
        tile_name = request.form.get(
            'tile_name',
            ''
        ).strip()
        tile_points = request.form.get('tile_points')
        tile_rules = request.form.get(
            'tile_rules',
            ''
        ).strip()

        completion_paths = request.form.getlist(
            'completion_path'
        )
        condition_types = request.form.getlist(
            'condition_type'
        )
        condition_triggers = request.form.getlist(
            'condition_trigger'
        )
        condition_targets = request.form.getlist(
            'condition_target'
        )

        if not tile_name:
            flash('Tile name is required.', 'danger')
            return redirect(
                url_for('tile_management.create_tile')
            )

        condition_count = len(condition_types)

        if not (
            condition_count
            == len(completion_paths)
            == len(condition_triggers)
            == len(condition_targets)
        ):
            flash(
                'The tile conditions were not submitted correctly.',
                'danger'
            )
            return redirect(
                url_for('tile_management.create_tile')
            )

        conditions = []

        try:
            for index in range(condition_count):
                conditions.append(
                    {
                        "completion_path":
                            int(completion_paths[index]),
                        "condition_type":
                            condition_types[index],
                        "condition_trigger":
                            condition_triggers[index],
                        "target":
                            int(condition_targets[index])
                    }
                )

            add_tile_with_conditions(
                tile_name,
                float(tile_points),
                tile_rules,
                conditions
            )

        except (TypeError, ValueError, KeyError) as error:
            flash(str(error), 'danger')
            return redirect(
                url_for('tile_management.create_tile')
            )

        flash(
            'Tile created successfully!',
            'success'
        )
        return redirect(
            url_for('tile_management.tile_list')
        )

    return render_template(
        'admin_templates/tile_templates/new_tile_form.html'
    )

@tile_routes.route(
    '/tiles/edit/<int:tile_id>',
    methods=['GET', 'POST']
)
@admin_required
def edit_tile(tile_id):
    tile = get_tile_by_id(tile_id)

    if tile is None:
        flash('Tile not found.', 'danger')
        return redirect(
            url_for('tile_management.tile_list')
        )

    if request.method == 'POST':
        tile_name = request.form.get(
            'tile_name',
            ''
        ).strip()

        tile_points = request.form.get(
            'tile_points'
        )

        tile_rules = request.form.get(
            'tile_rules',
            ''
        ).strip()

        completion_paths = request.form.getlist(
            'completion_path'
        )

        condition_types = request.form.getlist(
            'condition_type'
        )

        condition_triggers = request.form.getlist(
            'condition_trigger'
        )

        condition_targets = request.form.getlist(
            'condition_target'
        )

        if not tile_name:
            flash('Tile name is required.', 'danger')
            return redirect(
                url_for(
                    'tile_management.edit_tile',
                    tile_id=tile_id
                )
            )

        condition_count = len(condition_types)

        if not (
            condition_count
            == len(completion_paths)
            == len(condition_triggers)
            == len(condition_targets)
        ):
            flash(
                'The tile conditions were not submitted correctly.',
                'danger'
            )
            return redirect(
                url_for(
                    'tile_management.edit_tile',
                    tile_id=tile_id
                )
            )

        conditions = []

        try:
            for index in range(condition_count):
                conditions.append(
                    {
                        "completion_path":
                            int(completion_paths[index]),
                        "condition_type":
                            condition_types[index],
                        "condition_trigger":
                            condition_triggers[index],
                        "target":
                            int(condition_targets[index])
                    }
                )

            update_tile_with_conditions(
                tile_id,
                tile_name,
                float(tile_points),
                tile_rules,
                conditions
            )

        except (TypeError, ValueError, KeyError) as error:
            flash(str(error), 'danger')
            return redirect(
                url_for(
                    'tile_management.edit_tile',
                    tile_id=tile_id
                )
            )

        flash(
            'Tile updated successfully!',
            'success'
        )

        return redirect(
            url_for('tile_management.tile_list')
        )

    conditions = get_tile_conditions(tile_id)

    return render_template(
        'admin_templates/tile_templates/edit_tile.html',
        tile=tile,
        conditions=conditions
    )

@tile_routes.route('/tiles/delete/<int:tile_id>', methods=['POST'])
@admin_required
def delete_tile(tile_id):
    remove_tile(tile_id)
    flash('Tile deleted successfully!', 'success')
    return redirect(url_for('tile_management.tile_list'))


