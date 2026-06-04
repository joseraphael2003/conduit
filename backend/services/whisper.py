import asyncio
import logging
import time
from openai import OpenAI, APIConnectionError, APIStatusError

logger = logging.getLogger(__name__)


async def transcribe_audio(file_path: str) -> dict:
    """Call Whisper API with word-level timestamps. Retry on 5xx or connection errors."""
    max_retries = 3
    base_delay = 1.0
    multiplier = 2
    max_delay = 8.0

    def _transcribe():
        client = OpenAI(max_retries=0)
        with open(file_path, "rb") as audio_file:
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="verbose_json",
                timestamp_granularities=["word"]
            )
        return {"words": response.words}

    last_exception = None
    for attempt in range(max_retries + 1):
        try:
            return await asyncio.to_thread(_transcribe)
        except (APIConnectionError, APIStatusError) as exc:
            last_exception = exc
            if attempt >= max_retries:
                break
            if isinstance(exc, APIStatusError) and exc.status_code < 500:
                raise
            delay = min(base_delay * (multiplier ** attempt), max_delay)
            logger.warning(
                "Whisper API call failed (attempt %d/%d): %s. Retrying in %.1fs...",
                attempt + 1,
                max_retries + 1,
                exc,
                delay,
            )
            time.sleep(delay)
        except Exception:
            raise

    raise last_exception
