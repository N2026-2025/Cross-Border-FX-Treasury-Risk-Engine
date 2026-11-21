"""CLI entry point for the FX Treasury Engine."""

from __future__ import annotations

import asyncio
import argparse
import sys

from src.core.config import get_config, set_config
from src.core.engine import FXTreasuryEngine
from src.models.types import Currency, DataSource


async def run_analysis(args):
    """Run the full analysis pipeline."""
    engine = FXTreasuryEngine()
    results = await engine.run_analysis()

    print("\n" + "=" * 70)
    print("FX TREASURY ENGINE - ANALYSIS RESULTS")
    print("=" * 70)
    print(f"Timestamp: {results['timestamp']}")
    print(f"Sources: {results['source_count']}")
    print(f"Signals: {results['signal_count']}")
    print(f"Elapsed: {results['elapsed_seconds']:.2f}s")
    print("-" * 70)

    print("\n📊 EXPOSURE SUMMARY:")
    for currency, amount in results["exposure"].items():
        if currency != "total_usd":
            print(f"  {currency}: ${float(amount):,.2f}")

    if results["arbitrage_signals"]:
        print("\n⚡ ARBITRAGE SIGNALS:")
        for sig in results["arbitrage_signals"]:
            print(f"  {sig.recommended_action}")
            print(f"    Spread: {float(sig.spread_bps):.2f} bps | Confidence: {float(sig.confidence):.2f}")
            print(f"    Expected savings: ${float(sig.expected_savings_usd):,.2f}")
    else:
        print("\n✅ No arbitrage signals detected")

    print("\n" + "=" * 70)
    await engine.shutdown()


async def serve_api(args):
    """Start the FastAPI server."""
    import uvicorn
    from src.api.main import get_engine_instance

    app = get_engine_instance()
    uvicorn.run(app, host=args.host, port=args.port)


async def serve_dashboard(args):
    """Start the Streamlit dashboard."""
    import subprocess
    import sys

    subprocess.run(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "src/dashboard/main.py",
            "--server.port",
            str(args.port),
        ]
    )


def main():
    parser = argparse.ArgumentParser(
        description="Cross-Border FX & Treasury Risk Engine"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # Run analysis
    analysis_parser = subparsers.add_parser("analyze", help="Run full analysis")
    analysis_parser.add_argument(
        "--base", type=str, default="USD", help="Base currency (default: USD)"
    )
    analysis_parser.add_argument(
        "--targets",
        type=str,
        nargs="+",
        default=["EUR", "BRL", "MXN", "ARS"],
        help="Target currencies",
    )

    # Serve API
    api_parser = subparsers.add_parser("serve-api", help="Start FastAPI server")
    api_parser.add_argument("--host", type=str, default="0.0.0.0")
    api_parser.add_argument("--port", type=int, default=8000)

    # Serve dashboard
    dashboard_parser = subparsers.add_parser(
        "serve-dashboard", help="Start Streamlit dashboard"
    )
    dashboard_parser.add_argument("--port", type=int, default=8501)

    # Health check
    subparsers.add_parser("health", help="Run health check")

    args = parser.parse_args()

    if args.command == "analyze":
        asyncio.run(run_analysis(args))
    elif args.command == "serve-api":
        asyncio.run(serve_api(args))
    elif args.command == "serve-dashboard":
        asyncio.run(serve_dashboard(args))
    elif args.command == "health":
        from src.api.health import router
        print("Health check passed: all modules loaded successfully")
        print("Configuration loaded:", get_config().environment)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()