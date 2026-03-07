from __future__ import annotations

import argparse
import logging

from .config import BridgeConfig


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


def build_config(args: argparse.Namespace) -> BridgeConfig:
    return BridgeConfig(
        host=args.host,
        port=args.port,
        murmure_url=args.murmure_url,
        model_name=args.model_name,
        languages=args.languages or ["fr"],
        api_timeout=args.api_timeout,
        log_level=args.log_level,
    )


def configure_logging(log_level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
