import os


ALLOWED_EVIDENCE_EXTENSIONS = {
    '.png',
    '.jpg',
    '.jpeg',
    '.webp'
}


def resolve_dink_evidence_path(
    event_id,
    screenshot_path
):
    if not screenshot_path:
        return None

    try:
        event_id = int(event_id)

        if event_id <= 0:
            return None
    except (TypeError, ValueError):
        return None

    project_root = os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )

    evidence_directory = os.path.realpath(
        os.path.join(
            project_root,
            'uploads',
            'dink_evidence'
        )
    )

    absolute_path = os.path.realpath(
        os.path.join(
            project_root,
            str(screenshot_path)
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
        return None

    if common_path != evidence_directory:
        return None

    filename = os.path.basename(
        absolute_path
    )

    filename_root, extension = os.path.splitext(
        filename
    )

    if filename_root != f'dink_event_{event_id}':
        return None

    if (
        extension.lower()
        not in ALLOWED_EVIDENCE_EXTENSIONS
    ):
        return None

    if not os.path.isfile(
        absolute_path
    ):
        return None

    return absolute_path