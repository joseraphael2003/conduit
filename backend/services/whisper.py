import asyncio
from openai import OpenAI


async def transcribe_audio(file_path: str) -> dict:
    """Call Whisper API with word-level timestamps."""
    def _transcribe():
        client = OpenAI()
        with open(file_path, "rb") as audio_file:
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="verbose_json",
                timestamp_granularities=["word"]
            )
        return {"words": response.words}
    
    return await asyncio.to_thread(_transcribe)
