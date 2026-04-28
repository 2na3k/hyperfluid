#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys
from pathlib import Path

src_path = str(Path(__file__).resolve().parent / "src")
os.environ.setdefault("PYTHONPATH", src_path)

parser = argparse.ArgumentParser(description="hyperfluid backend")
parser.add_argument(
    "--source-type",
    default="coinbase",
    help="Exchange source (binance, hyperliquid, coinbase)",
)
parser.add_argument(
    "--symbol-list", default="BTC-USDC,ETH-USDC", help="Comma-separated symbol list"
)
args = parser.parse_args()

os.environ["HYPERFLUID_SOURCE_TYPE"] = args.source_type
os.environ["HYPERFLUID_SYMBOLS"] = args.symbol_list

cmd = [
    sys.executable,
    "-m",
    "uvicorn",
    "server.api.v1.main:app",
    "--host",
    "127.0.0.1",
    "--port",
    "3000",
    "--reload",
]
subprocess.run(cmd, env=os.environ)
