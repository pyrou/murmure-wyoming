from __future__ import annotations

import tempfile
import wave
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


@contextmanager
def temporary_wav_file(
    pcm: bytes,
    rate: int,
    width: int,
    channels: int,
) -> Iterator[Path]:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        with wave.open(str(tmp_path), "wb") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(width)
            wav_file.setframerate(rate)
            wav_file.writeframes(pcm)

        yield tmp_path
    finally:
        tmp_path.unlink(missing_ok=True)
