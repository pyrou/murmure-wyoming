from __future__ import annotations

import asyncio
import logging

from wyoming.event import Event, async_read_event, async_write_event
from wyoming.info import Describe

from .audio import temporary_wav_file
from .config import BridgeConfig
from .murmure_client import MurmureClient
from .session import SessionState
from .wyoming_info import build_info_event

_LOGGER = logging.getLogger("murmure_wyoming_bridge")


class MurmureWyomingBridge:
    def __init__(self, config: BridgeConfig) -> None:
        self.config = config
        self.murmure = MurmureClient(config.murmure_url, timeout=config.api_timeout)

    async def start(self) -> None:
        await self.murmure.start()
        server = await asyncio.start_server(
            self.handle_client,
            self.config.host,
            self.config.port,
        )
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

                await self._handle_event(event=event, data=data, writer=writer, state=state)

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

    async def _handle_event(
        self,
        event: Event,
        data: dict,
        writer: asyncio.StreamWriter,
        state: SessionState,
    ) -> None:
        if Describe.is_type(event.type) or event.type == "describe":
            await self._handle_describe(writer)
            return

        if event.type == "transcribe":
            state.start_transcription(
                language=data.get("language"),
                model_name=data.get("name"),
            )
            return

        if event.type == "audio-start":
            state.set_audio_format(
                rate=int(data["rate"]),
                width=int(data["width"]),
                channels=int(data["channels"]),
            )
            return

        if event.type == "audio-chunk":
            state.set_audio_format_from_defaults(
                rate=data.get("rate"),
                width=data.get("width"),
                channels=data.get("channels"),
            )
            if event.payload:
                state.append_audio_chunk(event.payload)
            return

        if event.type == "audio-stop":
            await self._handle_audio_stop(writer, state)
            return

        _LOGGER.debug("Ignoring unsupported event: %s", event.type)

    async def _handle_describe(self, writer: asyncio.StreamWriter) -> None:
        info_event = build_info_event(self.config)
        _LOGGER.debug("Sending info event: %s", info_event.data)
        await async_write_event(info_event, writer)

    async def _handle_audio_stop(
        self,
        writer: asyncio.StreamWriter,
        state: SessionState,
    ) -> None:
        if not state.transcribe_requested:
            _LOGGER.warning("Received audio-stop without prior transcribe")
            state.reset_all()
            return

        if not state.has_audio_format():
            _LOGGER.warning("Incomplete audio format information")
            await self._send_transcript(writer, text="", language=state.language)
            state.reset_all()
            return

        pcm = state.pcm_bytes()
        if not pcm:
            _LOGGER.info("Empty audio payload")
            await self._send_transcript(writer, text="", language=state.language)
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
            await self._send_transcript(
                writer,
                text=transcript,
                language=state.language,
            )
        except Exception:
            _LOGGER.exception("Transcription failed")
            await self._send_transcript(writer, text="", language=state.language)
        finally:
            state.reset_all()

    async def _send_transcript(
        self,
        writer: asyncio.StreamWriter,
        text: str,
        language: str | None = None,
    ) -> None:
        data = {"text": text}
        if language:
            data["language"] = language

        await async_write_event(Event(type="transcript", data=data), writer)

    async def _transcribe_pcm_to_text(
        self,
        pcm: bytes,
        rate: int | None,
        width: int | None,
        channels: int | None,
    ) -> str:
        if rate is None or width is None or channels is None:
            raise RuntimeError("Audio format is incomplete")

        with temporary_wav_file(
            pcm=pcm,
            rate=rate,
            width=width,
            channels=channels,
        ) as wav_path:
            return await self.murmure.transcribe_wav(wav_path)
