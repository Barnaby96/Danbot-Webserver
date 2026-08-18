from flask import Flask, render_template, request, redirect, url_for, flash, Blueprint

from routes.admin.admin_routes import admin_required
from utils.database import update_tile, remove_tile, get_tile_by_id, add_tile, get_tiles

tile_routes = Blueprint("tile_management", __name__)
ALLOWED_TILE_TYPES = {
    "DROP",
    "PET",
    "KILLCOUNT",
    "EXPERIENCE",
    "MANUAL",
}
@tile_routes.route('/tiles', methods=['GET'])
@admin_required
def tile_list():
    tiles = get_tiles()
    return render_template('admin_templates/tile_templates/tile_list.html', tiles=tiles)

@tile_routes.route('/tiles/new', methods=['GET', 'POST'])
@admin_required
def create_tile():
    if request.method == 'POST':
        tile_name = request.form.get('tile_name')
        tile_type = request.form.get('tile_type')
        if tile_type not in ALLOWED_TILE_TYPES:
            flash('Invalid tile type.', 'danger')
            return redirect(url_for('tile_management.create_tile'))
        tile_triggers = request.form.get('tile_triggers')
        tile_trigger_weights = request.form.get('tile_trigger_weights')
        tile_unique_drops = request.form.get('tile_unique_drops')
        tile_triggers_required = request.form.get('tile_triggers_required')
        tile_repetition = request.form.get('tile_repetition')
        tile_points = request.form.get('tile_points')
        tile_rules = request.form.get('tile_rules')

        add_tile(tile_name, tile_type, tile_triggers, tile_trigger_weights, tile_unique_drops, tile_triggers_required,
                 tile_repetition, tile_points, tile_rules)

        flash('Tile created successfully!', 'success')
        return redirect(url_for('tile_management.tile_list'))

    return render_template('admin_templates/tile_templates/new_tile_form.html')

@tile_routes.route('/tiles/edit/<int:tile_id>', methods=['GET', 'POST'])
@admin_required
def edit_tile(tile_id):
    tile = get_tile_by_id(tile_id)
    old_tile_triggers = tile[3]
    if request.method == 'POST':
        new_tile_id = request.form.get('tile_id')
        tile_name = request.form.get('tile_name')
        tile_type = request.form.get('tile_type')
        if tile_type not in ALLOWED_TILE_TYPES:
            flash('Invalid tile type.', 'danger')
            return redirect(url_for('tile_management.edit_tile', tile_id=tile_id))
        tile_triggers = request.form.get('tile_triggers')
        tile_trigger_weights = request.form.get('tile_trigger_weights')
        tile_unique_drops = request.form.get('tile_unique_drops')
        tile_triggers_required = request.form.get('tile_triggers_required')
        tile_repetition = request.form.get('tile_repetition')
        tile_points = request.form.get('tile_points')
        tile_rules = request.form.get('tile_rules')

        # Assuming you have a function to update the entire tile or update each field individually
        update_tile(tile_id,new_tile_id, tile_name, tile_type, old_tile_triggers, tile_triggers, tile_trigger_weights, tile_unique_drops, tile_triggers_required,
                    tile_repetition, tile_points, tile_rules)

        flash('Tile updated successfully!', 'success')
        return redirect(url_for('tile_management.tile_list'))

    return render_template('admin_templates/tile_templates/edit_tile.html', tile=tile)

@tile_routes.route('/tiles/delete/<int:tile_id>', methods=['POST'])
@admin_required
def delete_tile(tile_id):
    remove_tile(tile_id)
    flash('Tile deleted successfully!', 'success')
    return redirect(url_for('tile_management.tile_list'))


