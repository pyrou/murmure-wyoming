from __future__ import annotations

import asyncio

from .bridge import MurmureWyomingBridge
from .cli import build_config, configure_logging, parse_args


async def async_main() -> None:
    args = parse_args()
    config = build_config(args)
    configure_logging(config.log_level)

    bridge = MurmureWyomingBridge(config)
    try:
        await bridge.start()
    finally:
        await bridge.stop()


def main() -> None:
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        pass
