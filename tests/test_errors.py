from core.errors import friendly_error


def test_maps_known_errors():
    assert friendly_error("ERROR: [youtube] x: Sign in to confirm your age") == "This video is age-restricted, so it can't be downloaded."
    assert "blocking the server" in friendly_error("Sign in to confirm you’re not a bot.")
    assert friendly_error("ERROR: Private video. Sign in if you've been granted access") == "This video is private."
    assert "Pick another one" in friendly_error("Requested format is not available")
    assert friendly_error("ERROR: [youtube] aaaaaaaaaaa: This video is unavailable") == "This video is unavailable or has been removed."


def test_unknown_errors_get_a_generic_message():
    assert friendly_error("Traceback: KeyError 'foo'") == "This video couldn't be processed. Check the link and try again."
