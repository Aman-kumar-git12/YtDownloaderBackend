# Map raw yt-dlp errors to messages a user can act on. Order matters: more
# specific phrases come first ("confirm your age" also contains "Sign in to confirm").
FRIENDLY_ERRORS = [
    ("confirm your age", "This video is age-restricted, so it can't be downloaded."),
    ("Private video", "This video is private."),
    ("members-only", "This video is only available to channel members."),
    ("Join this channel", "This video is only available to channel members."),
    ("not available in your country", "This video isn't available in the server's region."),
    ("live event will begin", "This live stream hasn't started yet."),
    ("is live", "Live streams can't be downloaded until they end."),
    ("Requested format is not available", "That quality isn't available for this video. Pick another one."),
    ("Playlists and channels", "Playlists and channels aren't supported. Paste a link to a single video."),
    ("not a bot", "YouTube is temporarily blocking the server. Try again in a few minutes."),
    ("Video unavailable", "This video is unavailable or has been removed."),
    ("video is unavailable", "This video is unavailable or has been removed."),
    ("has been removed", "This video is unavailable or has been removed."),
    ("is not available", "That option isn't available for this video. Pick another one."),
]


def friendly_error(error):
    message = str(error).lower()
    for phrase, friendly in FRIENDLY_ERRORS:
        if phrase.lower() in message:
            return friendly
    return "This video couldn't be processed. Check the link and try again."
