from dotenv import load_dotenv

import requests


def get_track_info(token, track_id):
    """
    Fetches the Spotify track information for a given track ID using the provided bearer token.
    
    Args:
        token (str): The bearer token for authentication.
        track_id (str): The Spotify track ID.
    """

    response = requests.get(
        f"https://api.spotify.com/v1/tracks/{track_id}",
        headers={"Authorization": f"Bearer {token}"},
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
        f"https://api.reccobeats.com/v1/audio-features?ids={track_id}",
        headers= {'Accept': 'application/json'},
        timeout=10,
    )
    response.raise_for_status()

    return response.json()


if __name__ == "__main__":
    load_dotenv()  # Load environment variables from .env file
    import os

    token = os.getenv("BEARER_TOKEN")
    track_id = "2sFepQNyl1WjpROruP8bJ0"  # Example track ID
    track_info = get_track_info(token, track_id)
    print(track_info)

    audio_features = get_audio_features(track_id)
    print(audio_features)