from utils import database, db_entities, wom


def process_wom_competition():
    competition_id = database.get_wom_competition_id()

    if competition_id is None:
        return {
            "competition_id": None,
            "metrics_processed": 0,
            "players_processed": 0,
            "tiles_completed": [],
            "errors": []
        }

    conditions = database.get_wom_tile_conditions()

    metric_types = {
        (
            condition[3],
            str(condition[4]).strip().lower()
        )
        for condition in conditions
        if condition[4]
    }

    result = {
        "competition_id": competition_id,
        "metrics_processed": 0,
        "players_processed": 0,
        "tiles_completed": [],
        "errors": []
    }

    for condition_type, metric in sorted(metric_types):
        try:
            competition = wom.get_competition_details(
                competition_id,
                metric=metric
            )
        except wom.WiseOldManError as error:
            result["errors"].append(
                {
                    "metric": metric,
                    "error": str(error)
                }
            )
            continue

        result["metrics_processed"] += 1

        for participation in competition.get(
            "participations",
            []
        ):
            wom_player_id = participation.get("playerId")

            if wom_player_id is None:
                continue

            player_row = database.get_player_by_wom_player_id(
                wom_player_id
            )

            if player_row is None:
                result["errors"].append(
                    {
                        "metric": metric,
                        "wom_player_id": wom_player_id,
                        "error": (
                            "WOM participant is not linked "
                            "to a DanBot player."
                        )
                    }
                )
                continue

            player = db_entities.Player(player_row)

            progress = participation.get("progress") or {}
            current_gain = progress.get("gained")

            if current_gain is None:
                result["errors"].append(
                    {
                        "metric": metric,
                        "wom_player_id": wom_player_id,
                        "error": (
                            "WOM participation has no "
                            "gained progress value."
                        )
                    }
                )
                continue

            try:
                progress_result = (
                    database.apply_wom_metric_progress(
                        competition_id,
                        player.player_id,
                        condition_type,
                        metric,
                        current_gain
                    )
                )
            except (TypeError, ValueError) as error:
                result["errors"].append(
                    {
                        "metric": metric,
                        "wom_player_id": wom_player_id,
                        "error": str(error)
                    }
                )
                continue

            result["players_processed"] += 1

            for tile_result in progress_result["tiles"]:
                if not tile_result["ready"]:
                    continue

                try:
                    completed = (
                        database.complete_tile_with_contributions(
                            player.team_id,
                            tile_result["tile_id"]
                        )
                    )
                except ValueError as error:
                    result["errors"].append(
                        {
                            "metric": metric,
                            "tile_id": tile_result["tile_id"],
                            "error": str(error)
                        }
                    )
                    continue

                if completed:
                    result["tiles_completed"].append(
                        {
                            "tile_id": tile_result["tile_id"],
                            "team_id": player.team_id,
                            "metric": metric
                        }
                    )

    return result