import subprocess
from pathlib import Path

_CONFIG = str(Path(__file__).parent.parent / ".playwright" / "cli.config.json")


def pw(*args: str) -> str:
    cmd = list(args)
    # --config is only valid for the `open` subcommand
    if cmd and cmd[0] == "open":
        cmd = ["open", f"--config={_CONFIG}"] + cmd[1:]
    # --raw strips formatting so run-code/eval output can be parsed directly
    prefix = ["--raw"] if cmd and cmd[0] in ("run-code", "eval") else []
    result = subprocess.run(
        ["playwright-cli", *prefix, *cmd],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout
