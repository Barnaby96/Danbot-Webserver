from flask import Flask, render_template, request, redirect, url_for, flash, Blueprint

from routes.admin.admin_routes import admin_required
from utils.database import (
    remove_tile,
    get_tile_by_id,
    get_tile_conditions,
    get_tile_completion_paths,
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

        route_completion_paths = request.form.getlist(
            'route_completion_path'
        )
        route_modes = request.form.getlist(
            'route_mode'
        )
        route_targets = request.form.getlist(
            'route_target'
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

        route_count = len(route_modes)

        if not (
            route_count
            == len(route_completion_paths)
            == len(route_targets)
        ):
            flash(
                'The completion routes were not submitted correctly.',
                'danger'
            )
            return redirect(
                url_for('tile_management.create_tile')
            )

        conditions = []
        route_definitions = []

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

            for index in range(route_count):
                route_number = int(
                    route_completion_paths[index]
                )

                route_mode = str(
                    route_modes[index]
                ).strip().upper()

                if route_mode == "ALL":
                    route_target = None
                else:
                    route_target = int(
                        route_targets[index]
                    )

                require_unique = (
                    request.form.get(
                        f'route_require_unique_{route_number}'
                    )
                    is not None
                )

                route_definitions.append(
                    {
                        "completion_path":
                            route_number,
                        "route_mode":
                            route_mode,
                        "route_target":
                            route_target,
                        "require_unique":
                            require_unique
                    }
                )

            add_tile_with_conditions(
                tile_name,
                float(tile_points),
                tile_rules,
                conditions,
                completion_paths=route_definitions
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

        route_completion_paths = request.form.getlist(
            'route_completion_path'
        )

        route_modes = request.form.getlist(
            'route_mode'
        )

        route_targets = request.form.getlist(
            'route_target'
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

        route_count = len(route_modes)

        if not (
            route_count
            == len(route_completion_paths)
            == len(route_targets)
        ):
            flash(
                'The completion routes were not submitted correctly.',
                'danger'
            )
            return redirect(
                url_for(
                    'tile_management.edit_tile',
                    tile_id=tile_id
                )
            )

        conditions = []
        route_definitions = []

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

            for index in range(route_count):
                route_number = int(
                    route_completion_paths[index]
                )

                route_mode = str(
                    route_modes[index]
                ).strip().upper()

                if route_mode == "ALL":
                    route_target = None
                else:
                    route_target = int(
                        route_targets[index]
                    )

                require_unique = (
                    request.form.get(
                        f'route_require_unique_{route_number}'
                    )
                    is not None
                )

                route_definitions.append(
                    {
                        "completion_path":
                            route_number,
                        "route_mode":
                            route_mode,
                        "route_target":
                            route_target,
                        "require_unique":
                            require_unique
                    }
                )

            update_tile_with_conditions(
                tile_id,
                tile_name,
                float(tile_points),
                tile_rules,
                conditions,
                completion_paths=route_definitions
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
    completion_paths = get_tile_completion_paths(
        tile_id
    )

    return render_template(
        'admin_templates/tile_templates/edit_tile.html',
        tile=tile,
        conditions=conditions,
        completion_paths=completion_paths
    )

@tile_routes.route('/tiles/delete/<int:tile_id>', methods=['POST'])
@admin_required
def delete_tile(tile_id):
    remove_tile(tile_id)
    flash('Tile deleted successfully!', 'success')
    return redirect(url_for('tile_management.tile_list'))


