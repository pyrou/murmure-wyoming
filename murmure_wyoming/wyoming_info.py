from __future__ import annotations

from wyoming.event import Event
from wyoming.info import Attribution, AsrModel, AsrProgram, Info

from .config import BridgeConfig


def build_info_event(config: BridgeConfig) -> Event:
    attribution = Attribution(
        name=config.attribution_name,
        url=config.attribution_url,
    )

    info = Info(
        asr=[
            AsrProgram(
                name=config.model_name,
                attribution=attribution,
                installed=True,
                description="Wyoming bridge over Murmure HTTP API",
                version="1.0.0",
                models=[
                    AsrModel(
                        name=config.model_name,
                        attribution=attribution,
                        installed=True,
                        description="Murmure HTTP transcription",
                        version="1.0.0",
                        languages=config.languages,
                    )
                ],
                supports_transcript_streaming=False,
            )
        ]
    )

    return info.event()
