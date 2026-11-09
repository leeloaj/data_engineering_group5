import os
from time import monotonic

import requests
from dotenv import load_dotenv


def spotify_token_provider():
    """Return a callable that supplies an access token and renews app tokens."""
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    if not client_id and not client_secret:
        token = os.getenv("SPOTIFY_ACCESS_TOKEN")
        if token:
            return lambda: token
    if not client_id or not client_secret:
        raise ValueError(
            "Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET, or set SPOTIFY_ACCESS_TOKEN"
        )

    token = None
    refresh_at = 0

    def get_token():
        nonlocal token, refresh_at
        if token is None or monotonic() >= refresh_at:
            response = requests.post(
                "https://accounts.spotify.com/api/token",
                auth=(client_id, client_secret),
                data={"grant_type": "client_credentials"},
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()
            token = payload["access_token"]
            refresh_at = monotonic() + max(0, payload["expires_in"] - 30)
        return token

    return get_token


def get_track_info(token, track_id, market=None):
    """
    Fetches the Spotify track information for a given track ID using the provided bearer token.
    
    Args:
        token (str): The bearer token for authentication.
        track_id (str): The Spotify track ID.
        market (str or None): Optional ISO country code for catalog availability.
    """

    response = requests.get(
        f"https://api.spotify.com/v1/tracks/{track_id}",
        headers={"Authorization": f"Bearer {token}"},
        params={"market": market} if market else None,
        timeout=10,
    )
    response.raise_for_status()

    return response.json()

def get_audio_features(track_id):
    """
    Fetches audio features from the ReccoBeats API.

    Args:
        track_id (str): The Spotify track ID.
    """
    response = requests.get(
        "https://api.reccobeats.com/v1/audio-features",
        params={"ids": track_id},
        headers={"Accept": "application/json"},
        timeout=10,
    )
    response.raise_for_status()

    return response.json()


if __name__ == "__main__":
    load_dotenv()  # Load environment variables from .env file
    token = os.getenv("BEARER_TOKEN")
    track_id = "2sFepQNyl1WjpROruP8bJ0"  # Example track ID
    track_info = get_track_info(token, track_id)
    print(track_info)

    audio_features = get_audio_features(track_id)
    print(audio_features)
