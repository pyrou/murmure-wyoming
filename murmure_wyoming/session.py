from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SessionState:
    transcribe_requested: bool = False
    language: Optional[str] = None
    model_name: Optional[str] = None

    rate: Optional[int] = None
    width: Optional[int] = None
    channels: Optional[int] = None

    audio_chunks: list[bytes] = field(default_factory=list)

    def start_transcription(
        self,
        language: Optional[str],
        model_name: Optional[str],
    ) -> None:
        self.transcribe_requested = True
        self.language = language
        self.model_name = model_name
        self.reset_audio()

    def set_audio_format(self, rate: int, width: int, channels: int) -> None:
        self.rate = rate
        self.width = width
        self.channels = channels

    def set_audio_format_from_defaults(
        self,
        rate: Optional[int],
        width: Optional[int],
        channels: Optional[int],
    ) -> None:
        if self.rate is None:
            self.rate = int(rate or 16000)
        if self.width is None:
            self.width = int(width or 2)
        if self.channels is None:
            self.channels = int(channels or 1)

    def append_audio_chunk(self, chunk: bytes) -> None:
        self.audio_chunks.append(chunk)

    def has_audio_format(self) -> bool:
        return (
            self.rate is not None
            and self.width is not None
            and self.channels is not None
        )

    def pcm_bytes(self) -> bytes:
        return b"".join(self.audio_chunks)

    def reset_audio(self) -> None:
        self.rate = None
        self.width = None
        self.channels = None
        self.audio_chunks.clear()

    def reset_all(self) -> None:
        self.transcribe_requested = False
        self.language = None
        self.model_name = None
        self.reset_audio()
