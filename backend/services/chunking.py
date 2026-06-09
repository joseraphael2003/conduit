import os
import tempfile
from typing import List, Tuple
from pydub import AudioSegment
from pydub.silence import detect_nonsilent


def estimate_wav_size(audio_segment: AudioSegment) -> int:
    """Rough estimate of WAV file size based on duration and sample rate."""
    duration_seconds = len(audio_segment) / 1000.0
    bytes_per_second = audio_segment.frame_rate * audio_segment.channels * audio_segment.sample_width
    # Add 44 bytes for standard WAV header
    return int(bytes_per_second * duration_seconds) + 44


def chunk_audio(file_path: str, max_bytes: int = 25_000_000) -> List[Tuple[str, float]]:
    """Split audio on silence boundaries, each chunk <= max_bytes.

    Returns a list of (chunk_path, start_offset_seconds) tuples, where
    start_offset_seconds is the chunk's start position in the ORIGINAL audio.
    Callers must add the offset to each transcribed word's start/end so
    timestamps stay on the absolute timeline. Single-chunk paths use offset 0.0.
    """
    audio = AudioSegment.from_file(file_path)

    # If the whole audio is already under the limit, return as single chunk
    if estimate_wav_size(audio) <= max_bytes:
        temp_dir = tempfile.mkdtemp()
        chunk_path = os.path.join(temp_dir, "chunk_000.wav")
        audio.export(chunk_path, format="wav")
        return [(chunk_path, 0.0)]

    # Detect non-silent segments with >= 300ms silence between them
    nonsilent_ranges = detect_nonsilent(audio, min_silence_len=300, silence_thresh=-40)

    # If no non-silent segments found, export the whole audio as one chunk
    # (caller is responsible for handling oversized files)
    if not nonsilent_ranges:
        temp_dir = tempfile.mkdtemp()
        chunk_path = os.path.join(temp_dir, "chunk_000.wav")
        audio.export(chunk_path, format="wav")
        return [(chunk_path, 0.0)]

    temp_dir = tempfile.mkdtemp()
    chunk_paths = []
    current_chunk_start = nonsilent_ranges[0][0]
    current_chunk_end = nonsilent_ranges[0][1]

    for i in range(1, len(nonsilent_ranges)):
        start, end = nonsilent_ranges[i]

        # Try extending the current chunk to include this segment
        candidate_chunk = audio[current_chunk_start:end]
        if estimate_wav_size(candidate_chunk) > max_bytes:
            # Export current chunk
            chunk_path = os.path.join(temp_dir, f"chunk_{len(chunk_paths):03d}.wav")
            audio[current_chunk_start:current_chunk_end].export(chunk_path, format="wav")
            chunk_paths.append((chunk_path, current_chunk_start / 1000.0))

            # Start new chunk
            current_chunk_start = start
            current_chunk_end = end
        else:
            # Extend current chunk to include the silence gap and this segment
            current_chunk_end = end

    # Export the final chunk
    chunk_path = os.path.join(temp_dir, f"chunk_{len(chunk_paths):03d}.wav")
    audio[current_chunk_start:current_chunk_end].export(chunk_path, format="wav")
    chunk_paths.append((chunk_path, current_chunk_start / 1000.0))

    return chunk_paths
