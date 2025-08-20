"""Main entry point for I3 Gateway."""

import asyncio
import signal
import sys
from pathlib import Path

import click
import structlog
from dotenv import load_dotenv


# Add parent directory to path if running as module
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import load_config
from src.gateway import I3Gateway
from src.utils.logging import setup_logging


logger = structlog.get_logger()


def handle_signal(sig: int, gateway: I3Gateway | None) -> None:
    """Handle shutdown signals."""
    sig_name = signal.Signals(sig).name
    logger.info(f"Received {sig_name}, shutting down...")
    if gateway:
        asyncio.create_task(gateway.shutdown())


@click.command()
@click.option(
    "-c",
    "--config",
    type=click.Path(exists=True, path_type=Path),
    default="config/config.yaml",
    help="Path to configuration file",
)
@click.option(
    "-e",
    "--env-file",
    type=click.Path(exists=True, path_type=Path),
    default=".env",
    help="Path to environment file",
)
@click.option("--debug", is_flag=True, help="Enable debug mode")
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    help="Override log level from config",
)
@click.option("--dry-run", is_flag=True, help="Validate configuration without starting the gateway")
@click.version_option()
def main(
    config: Path, env_file: Path, debug: bool, log_level: str | None, dry_run: bool
) -> None:
    """I3 Gateway - Intermud3 Protocol Gateway Service.

    This service acts as a bridge between MUDs and the global Intermud-3 network,
    handling protocol complexity internally while exposing a simple JSON-RPC API.
    """
    # Load environment variables
    if env_file.exists():
        load_dotenv(env_file)

    # Load configuration
    try:
        settings = load_config(config)
        if debug:
            settings.development.debug = True
        if log_level:
            settings.logging.level = log_level
    except Exception as e:
        click.echo(f"Error loading configuration: {e}", err=True)
        sys.exit(1)

    # Setup logging
    setup_logging(
        level=settings.logging.level,
        format_type=settings.logging.format,
        log_file=settings.logging.file if not dry_run else None,
    )

    logger.info(
        "Starting I3 Gateway",
        version=__import__("i3_gateway").__version__,
        config_file=str(config),
        debug=debug or settings.development.debug,
    )

    # Validate configuration
    if dry_run:
        logger.info("Configuration validated successfully")
        click.echo("Configuration is valid!")
        sys.exit(0)

    # Create and run gateway
    try:
        gateway = I3Gateway(settings)

        # Setup signal handlers
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda s, f: handle_signal(s, gateway))

        # Run the gateway
        loop.run_until_complete(gateway.start())
        loop.run_forever()

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.exception("Fatal error", error=str(e))
        sys.exit(1)
    finally:
        if "gateway" in locals():
            loop.run_until_complete(gateway.shutdown())
        loop.close()
        logger.info("I3 Gateway stopped")


if __name__ == "__main__":
    main()
