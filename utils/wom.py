import os

import requests


class WiseOldManError(Exception):
    """Raised when Wise Old Man data cannot be retrieved."""


def get_group_member(rsn):
    group_id = os.getenv("WOM_GROUP_ID")
    if not group_id:
        raise WiseOldManError("WOM_GROUP_ID is not configured.")

    headers = {
        "User-Agent": os.getenv(
            "WOM_USER_AGENT",
            "DanBot Development"
        )
    }

    api_key = os.getenv("WOM_KEY")
    if api_key:
        headers["x-api-key"] = api_key

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