"""SRT generation service for transcription output."""

import json
import os
import re
from typing import List

import srt
from srt import timedelta
from config import PROJECTS_BASE_DIR


def _split_into_sentences(words: List[dict]) -> List[dict]:
    """Group words into sentences at punctuation boundaries (. ? !)."""
    sentences = []
    current_sentence = []
    current_start = None

    for word_info in words:
        word = word_info.get("word", "")
        start = word_info.get("start")
        end = word_info.get("end")

        if current_start is None:
            current_start = start

        current_sentence.append({
            "word": word,
            "start": start,
            "end": end,
        })

        if re.search(r"[.?!]\s*$", word):
            sentences.append({
                "words": current_sentence,
                "start": current_start,
                "end": current_sentence[-1]["end"],
            })
            current_sentence = []
            current_start = None

    # Handle trailing words without punctuation
    if current_sentence:
        sentences.append({
            "words": current_sentence,
            "start": current_start,
            "end": current_sentence[-1]["end"],
        })

    return sentences


def _wrap_line(text: str, max_length: int = 42) -> str:
    """Wrap text so that each line is <= max_length characters."""
    words = text.split()
    lines = []
    current_line = ""

    for word in words:
        if not current_line:
            current_line = word
        elif len(current_line) + 1 + len(word) <= max_length:
            current_line += " " + word
        else:
            lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    return "\n".join(lines)


def generate_srt(words: List[dict]) -> str:
    """Generate SRT from word-level timestamps.

    Groups words into sentences (split at . ? !), uses 1 sentence
    per caption for clarity, and ensures each line is <= 42 characters.
    """
    sentences = _split_into_sentences(words)
    subtitles = []
    index = 1

    i = 0
    while i < len(sentences):
        # Take 1 sentence per caption for clarity
        group = [sentences[i]]

        # Build text and compute time range
        text_parts = []
        start_time = group[0]["start"]
        end_time = group[-1]["end"]

        for sent in group:
            sentence_text = " ".join(w["word"] for w in sent["words"])
            text_parts.append(sentence_text)

        text = " ".join(text_parts)
        wrapped_text = _wrap_line(text, max_length=42)

        # Convert seconds to timedelta
        start_delta = timedelta(seconds=start_time)
        end_delta = timedelta(seconds=end_time)

        subtitle = srt.Subtitle(
            index=index,
            start=start_delta,
            end=end_delta,
            content=wrapped_text,
        )
        subtitles.append(subtitle)

        index += 1
        i += len(group)

    return srt.compose(subtitles)


def save_transcription_files(
    uuid: str, words: List[dict], srt_content: str, transcript: str
) -> None:
    """Save all transcription output files to project directory.

    Saves:
      - captions.srt
      - transcript_raw.txt
      - .conduit/source_of_truth_script.txt
      - .conduit/words.json
    """
    project_dir = os.path.join(PROJECTS_BASE_DIR, uuid)
    os.makedirs(project_dir, exist_ok=True)

    srt_path = os.path.join(project_dir, "captions.srt")
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(srt_content)

    transcript_path = os.path.join(project_dir, "transcript_raw.txt")
    with open(transcript_path, "w", encoding="utf-8") as f:
        f.write(transcript)

    # Save source of truth script and words for downstream steps
    conduit_dir = os.path.join(project_dir, ".conduit")
    os.makedirs(conduit_dir, exist_ok=True)
    script_path = os.path.join(conduit_dir, "source_of_truth_script.txt")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(transcript)

    words_data = {"words": words}
    words_conduit_path = os.path.join(conduit_dir, "words.json")
    with open(words_conduit_path, "w", encoding="utf-8") as f:
        json.dump(words_data, f, indent=2)
