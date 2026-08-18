import os

import requests


class WiseOldManError(Exception):
    """Raised when Wise Old Man data cannot be retrieved."""


def _get_headers():
    headers = {
        "User-Agent": os.getenv(
            "WOM_USER_AGENT",
            "DanBot Development"
        )
    }

    api_key = os.getenv("WOM_KEY")
    if api_key:
        headers["x-api-key"] = api_key

    return headers


def get_group_member(rsn):
    group_id = os.getenv("WOM_GROUP_ID")
    if not group_id:
        raise WiseOldManError("WOM_GROUP_ID is not configured.")

    headers = _get_headers()

    try:
        response = requests.get(
            f"https://api.wiseoldman.net/v2/groups/{group_id}",
            headers=headers,
            timeout=20
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as error:
        raise WiseOldManError(
            "Unable to retrieve the Wise Old Man group."
        ) from error

    requested_rsn = rsn.strip().lower()

    for membership in data.get("memberships", []):
        player = membership.get("player") or {}

        username = str(player.get("username", "")).strip()
        display_name = str(player.get("displayName", "")).strip()

        if requested_rsn in {
            username.lower(),
            display_name.lower()
        }:
            return player

    return None


def get_competition_details(competition_id, metric=None):
    try:
        competition_id = int(competition_id)
    except (TypeError, ValueError) as error:
        raise WiseOldManError(
            "The Wise Old Man competition ID must be a number."
        ) from error

    params = {}
    if metric:
        params["metric"] = metric

    try:
        response = requests.get(
            f"https://api.wiseoldman.net/v2/competitions/{competition_id}",
            headers=_get_headers(),
            params=params,
            timeout=20
        )

        if response.status_code == 404:
            raise WiseOldManError(
                f"Wise Old Man competition {competition_id} was not found."
            )

        response.raise_for_status()
        data = response.json()

    except WiseOldManError:
        raise
    except (requests.RequestException, ValueError) as error:
        raise WiseOldManError(
            "Unable to retrieve the Wise Old Man competition."
        ) from error

    return data
