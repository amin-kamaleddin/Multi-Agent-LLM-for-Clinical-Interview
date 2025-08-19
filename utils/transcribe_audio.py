from openai import OpenAI


# @traceable(name="audio_transcription")
def transcribe_audio_file(file_path: str) -> str:
    """
    Transcribe audio file using OpenAI Whisper

    Args:
        file_path: Path to the audio file

    Returns:
        Transcribed text
    """
    client = OpenAI()

    try:
        with open(file_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="gpt-4o-mini-transcribe",
                file=audio_file,
                response_format="text"
            )
        return transcript.strip()
    except Exception as e:
        print(f"Error transcribing audio: {e}")
        return ""
