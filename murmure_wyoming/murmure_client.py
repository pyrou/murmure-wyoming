from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import aiohttp


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
                    f"Murmure a renvoye un JSON invalide: {text[:500]}"
                ) from err

            if "error" in payload:
                raise RuntimeError(f"Murmure error: {payload['error']}")

            transcript = payload.get("text")
            if not isinstance(transcript, str):
                raise RuntimeError(f"Reponse Murmure inattendue: {payload!r}")

            return transcript
