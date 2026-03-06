#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import tempfile
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import aiohttp
from wyoming.event import Event, async_read_event, async_write_event
from wyoming.info import Attribution, AsrModel, AsrProgram, Describe, Info


_LOGGER = logging.getLogger("murmure_wyoming_bridge")


@dataclass
class SessionState:
    transcribe_requested: bool = False
    language: Optional[str] = None
    model_name: Optional[str] = None

    rate: Optional[int] = None
    width: Optional[int] = None
    channels: Optional[int] = None

    audio_chunks: list[bytes] = field(default_factory=list)

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

    def pcm_bytes(self) -> bytes:
        return b"".join(self.audio_chunks)


class MurmureClient:
    def __init__(self, api_url: str, timeout: float = 120.0) -> None:
        self.api_url = api_url
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: Optional[aiohttp.ClientSession] = None

    async def start(self) -> None:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)

    async def stop(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def transcribe_wav(self, wav_path: Path) -> str:
        if self._session is None or self._session.closed:
            await self.start()

        assert self._session is not None

        form = aiohttp.FormData()
        form.add_field(
            "audio",
            wav_path.read_bytes(),
            filename=wav_path.name,
            content_type="audio/wav",
        )

        async with self._session.post(self.api_url, data=form) as response:
            text = await response.text()

            if response.status >= 400:
                raise RuntimeError(f"Murmure HTTP {response.status}: {text[:500]}")

            try:
                payload = json.loads(text)
            except json.JSONDecodeError as err:
                raise RuntimeError(
                    f"Murmure a renvoyé un JSON invalide: {text[:500]}"
                ) from err

            if "error" in payload:
                raise RuntimeError(f"Murmure error: {payload['error']}")

            transcript = payload.get("text")
            if not isinstance(transcript, str):
                raise RuntimeError(f"Réponse Murmure inattendue: {payload!r}")

            return transcript


class MurmureWyomingBridge:
    def __init__(
        self,
        host: str,
        port: int,
        murmure_url: str,
        model_name: str,
        languages: list[str],
        attribution_name: str = "Kieirra / Murmure",
        attribution_url: str = "https://github.com/Kieirra/murmure",
        api_timeout: float = 120.0,
    ) -> None:
        self.host = host
        self.port = port
        self.model_name = model_name
        self.languages = languages
        self.attribution_name = attribution_name
        self.attribution_url = attribution_url
        self.murmure = MurmureClient(murmure_url, timeout=api_timeout)

    async def start(self) -> None:
        await self.murmure.start()
        server = await asyncio.start_server(self.handle_client, self.host, self.port)
        sockets = ", ".join(str(sock.getsockname()) for sock in (server.sockets or []))
        _LOGGER.info("Listening on %s", sockets)

        async with server:
            await server.serve_forever()

    async def stop(self) -> None:
        await self.murmure.stop()

    async def handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        peer = writer.get_extra_info("peername")
        _LOGGER.info("Client connected: %s", peer)

        state = SessionState()

        try:
            while True:
                event = await async_read_event(reader)
                if event is None:
                    break

                data = event.data or {}
                _LOGGER.debug(
                    "Received event=%s data=%s payload=%dB",
                    event.type,
                    data,
                    0 if event.payload is None else len(event.payload),
                )

                if Describe.is_type(event.type) or event.type == "describe":
                    await self.handle_describe(writer)
                    continue

                if event.type == "transcribe":
                    state.transcribe_requested = True
                    state.language = data.get("language")
                    state.model_name = data.get("name")
                    state.reset_audio()
                    continue

                if event.type == "audio-start":
                    state.rate = int(data["rate"])
                    state.width = int(data["width"])
                    state.channels = int(data["channels"])
                    continue

                if event.type == "audio-chunk":
                    if state.rate is None:
                        state.rate = int(data.get("rate") or 16000)
                    if state.width is None:
                        state.width = int(data.get("width") or 2)
                    if state.channels is None:
                        state.channels = int(data.get("channels") or 1)

                    if event.payload:
                        state.audio_chunks.append(event.payload)
                    continue

                if event.type == "audio-stop":
                    await self.handle_audio_stop(writer, state)
                    continue

                _LOGGER.debug("Ignoring unsupported event: %s", event.type)

        except asyncio.IncompleteReadError:
            pass
        except Exception:
            _LOGGER.exception("Client error: %s", peer)
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            _LOGGER.info("Client disconnected: %s", peer)

    async def handle_describe(self, writer: asyncio.StreamWriter) -> None:
        attribution = Attribution(
            name=self.attribution_name,
            url=self.attribution_url,
        )

        info = Info(
            asr=[
                AsrProgram(
                    name=self.model_name,
                    attribution=attribution,
                    installed=True,
                    description="Wyoming bridge over Murmure HTTP API",
                    version="1.0.0",
                    models=[
                        AsrModel(
                            name=self.model_name,
                            attribution=attribution,
                            installed=True,
                            description="Murmure HTTP transcription",
                            version="1.0.0",
                            languages=self.languages,
                        )
                    ],
                    supports_transcript_streaming=False,
                )
            ]
        )

        info_event = info.event()
        _LOGGER.debug("Sending info event: %s", info_event.data)
        await async_write_event(info_event, writer)

    async def handle_audio_stop(
        self,
        writer: asyncio.StreamWriter,
        state: SessionState,
    ) -> None:
        if not state.transcribe_requested:
            _LOGGER.warning("Received audio-stop without prior transcribe")
            state.reset_all()
            return

        if state.rate is None or state.width is None or state.channels is None:
            _LOGGER.warning("Incomplete audio format information")
            await self.send_transcript(writer, text="", language=state.language)
            state.reset_all()
            return

        pcm = state.pcm_bytes()
        if not pcm:
            _LOGGER.info("Empty audio payload")
            await self.send_transcript(writer, text="", language=state.language)
            state.reset_all()
            return

        try:
            transcript = await self._transcribe_pcm_to_text(
                pcm=pcm,
                rate=state.rate,
                width=state.width,
                channels=state.channels,
            )
            _LOGGER.info("Transcript: %r", transcript)
            await self.send_transcript(
                writer,
                text=transcript,
                language=state.language,
            )
        except Exception:
            _LOGGER.exception("Transcription failed")
            await self.send_transcript(writer, text="", language=state.language)
        finally:
            state.reset_all()

    async def send_transcript(
        self,
        writer: asyncio.StreamWriter,
        text: str,
        language: Optional[str] = None,
    ) -> None:
        data = {"text": text}
        if language:
            data["language"] = language

        await async_write_event(Event(type="transcript", data=data), writer)

    async def _transcribe_pcm_to_text(
        self,
        pcm: bytes,
        rate: int,
        width: int,
        channels: int,
    ) -> str:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            with wave.open(str(tmp_path), "wb") as wav_file:
                wav_file.setnchannels(channels)
                wav_file.setsampwidth(width)
                wav_file.setframerate(rate)
                wav_file.writeframes(pcm)

            return await self.murmure.transcribe_wav(tmp_path)
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                _LOGGER.warning("Could not delete temp file: %s", tmp_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Wyoming STT bridge for Murmure HTTP API"
    )
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, default=10300, help="Bind port")
    parser.add_argument(
        "--murmure-url",
        default="http://127.0.0.1:4800/api/transcribe",
        help="Murmure transcription endpoint",
    )
    parser.add_argument(
        "--model-name",
        default="murmure",
        help="Model name exposed to Home Assistant",
    )
    parser.add_argument(
        "--language",
        action="append",
        dest="languages",
        default=None,
        help="Supported language, repeatable (example: --language fr --language en)",
    )
    parser.add_argument(
        "--api-timeout",
        type=float,
        default=120.0,
        help="Timeout in seconds for Murmure HTTP API",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )
    return parser.parse_args()


async def async_main() -> None:
    args = parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    languages = args.languages or ["fr"]

    bridge = MurmureWyomingBridge(
        host=args.host,
        port=args.port,
        murmure_url=args.murmure_url,
        model_name=args.model_name,
        languages=languages,
        api_timeout=args.api_timeout,
    )

    try:
        await bridge.start()
    finally:
        await bridge.stop()


def main() -> None:
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()