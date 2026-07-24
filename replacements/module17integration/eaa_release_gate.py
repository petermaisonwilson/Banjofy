from __future__ import annotations

from pathlib import Path
import json

from banjofy.download.audio_downloader import DownloadManager


class DummyResult:
    url = "https://example.invalid/test"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    manager = DownloadManager()
    health = manager.health_check()
    print(json.dumps(health, indent=2))

    require(bool(health.get("ready")), "EAA health_check did not report ready")

    command = manager._command(DummyResult(), Path("Audio"), "test")
    require(bool(command), "EAA command is empty")

    executable = Path(command[0]).resolve()
    expected_executable = Path(str(health["yt_dlp"])).resolve()
    require(
        executable == expected_executable,
        f"EAA executable mismatch: command={executable} health={expected_executable}",
    )

    required_switches = {
        "--plugin-dirs": Path(str(health["plugin_root"])).resolve(),
        "--js-runtimes": Path(str(health["node"])).resolve(),
        "--ffmpeg-location": Path(str(health["agent_root"])).resolve(),
    }

    for switch, expected_path in required_switches.items():
        require(switch in command, f"Required EAA switch missing: {switch}")
        index = command.index(switch)
        require(index + 1 < len(command), f"No value follows EAA switch: {switch}")
        raw_value = command[index + 1]
        if switch == "--js-runtimes":
            require(
                raw_value.startswith("node:"),
                f"Unexpected --js-runtimes value: {raw_value}",
            )
            raw_value = raw_value.split(":", 1)[1]
        actual_path = Path(raw_value).resolve()
        require(
            actual_path == expected_path,
            f"{switch} path mismatch: command={actual_path} expected={expected_path}",
        )

    require(
        bool(health.get("provider_compiled_generator")),
        "Compiled build/generate_once.js is missing",
    )

    require(
        "--extractor-args" in command,
        "EAA command does not contain extractor arguments",
    )
    require(
        any("youtubepot-bgutilscript:" in value for value in command),
        "EAA command does not contain the bgutil provider configuration",
    )
    require(
        command[-1] == DummyResult.url,
        "Selected URL is not the final EAA command argument",
    )

    print("Banjofy-to-EAA handoff release gate: passed")


if __name__ == "__main__":
    main()
