"""CLI voice commands — push-to-talk Nexi on gate7."""

from __future__ import annotations

import base64
import json
import os

import httpx
import typer

from .client import XnchCliClient
from .util import format_http_error
from .voice_io import (
    describe_input_device,
    describe_output_device,
    is_silent_pcm,
    list_devices,
    pcm_stats,
    pcm_to_wav_bytes,
    play_wav,
    record_seconds,
)

voice_app = typer.Typer(help="Voice interaction with Nexi (STT + TTS on gate7).")

_MIC_HINTS = (
    "Mic captured silence. Try:\n"
    "  • System Settings → Privacy → Microphone → allow your terminal app\n"
    "  • python3 -m cli voice mic-test\n"
    "  • export XNCH_VOICE_INPUT_DEVICE=<index>  (see voice devices)"
)


def _client() -> XnchCliClient:
    return XnchCliClient()


def _mute() -> bool:
    return os.environ.get("XNCH_VOICE_MUTE", "").lower() in {"1", "true", "yes"}


def _fail(exc: Exception) -> None:
    if isinstance(exc, httpx.HTTPStatusError):
        msg = format_http_error(exc)
        typer.secho(msg, fg=typer.colors.RED, err=True)
        if "Empty transcript" in msg or "silence" in msg.lower():
            typer.secho(_MIC_HINTS, fg=typer.colors.YELLOW, err=True)
    else:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
    raise typer.Exit(code=1)


def _warn_silent_capture(pcm: bytes) -> None:
    stats = pcm_stats(pcm)
    typer.echo(
        f"  mic {describe_input_device()} — peak={stats['peak']:.0f} rms={stats['rms']:.0f}"
    )
    if is_silent_pcm(pcm):
        typer.secho(
            "  ⚠ no audio detected — speak louder or check mic permission",
            fg=typer.colors.YELLOW,
        )


@voice_app.command("devices")
def devices(json_out: bool = typer.Option(False, "--json", help="Output raw JSON")) -> None:
    """List sounddevice input/output devices."""
    try:
        devs = list_devices()
    except Exception as exc:
        typer.secho(f"sounddevice error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    if json_out:
        typer.echo(json.dumps(devs, indent=2))
        return

    typer.echo(f"Active input: {describe_input_device()}")
    typer.echo(f"Active output: {describe_output_device()}")
    for dev in devs:
        typer.echo(
            f"[{dev['index']}] {dev['name']} "
            f"(in={dev['max_input_channels']} out={dev['max_output_channels']})"
        )


@voice_app.command("mic-test")
def mic_test(
    seconds: float = typer.Option(2.0, "--seconds", "-s", help="Recording duration"),
    save: str | None = typer.Option(None, "--save", help="Write WAV for debugging"),
) -> None:
    """Record briefly and show input level (mic permission / device check)."""
    typer.echo(f"Mic: {describe_input_device()}")
    typer.echo(f"Speak now — recording {seconds:.1f}s…")
    try:
        pcm = record_seconds(seconds)
    except Exception as exc:
        _fail(exc)

    stats = pcm_stats(pcm)
    typer.echo(
        f"peak={stats['peak']:.0f}  rms={stats['rms']:.0f}  "
        f"duration={stats['duration_s']:.1f}s"
    )
    if is_silent_pcm(pcm):
        typer.secho("FAIL: silence detected — grant mic access or pick XNCH_VOICE_INPUT_DEVICE", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    typer.secho("OK: microphone is capturing audio", fg=typer.colors.GREEN)
    if save:
        wav = pcm_to_wav_bytes(pcm)
        with open(save, "wb") as f:
            f.write(wav)
        typer.echo(f"Wrote {save}")


@voice_app.command("listen")
def listen(
    seconds: float = typer.Option(5.0, "--seconds", "-s", help="Recording duration"),
    json_out: bool = typer.Option(False, "--json", help="Output raw JSON"),
) -> None:
    """Record and transcribe only (POST /nexi/voice/transcribe)."""
    typer.echo(f"Speak now — recording {seconds:.1f}s…")
    try:
        pcm = record_seconds(seconds)
    except Exception as exc:
        _fail(exc)

    _warn_silent_capture(pcm)
    wav = pcm_to_wav_bytes(pcm)

    try:
        with _client() as client:
            data = client.voice_transcribe(wav)
    except Exception as exc:
        _fail(exc)

    if json_out:
        typer.echo(json.dumps(data, indent=2))
        return
    typer.echo(data.get("transcript", ""))


@voice_app.command("speaker-test")
def speaker_test(
    text: str = typer.Option("Speaker test.", "--text", "-t", help="Phrase to synthesize"),
) -> None:
    """Fetch TTS from gate7 and play on the resolved output device."""
    typer.echo(f"Output: {describe_output_device()}")
    try:
        with _client() as client:
            wav = client.voice_speak(text)
    except Exception as exc:
        _fail(exc)

    typer.echo("♪ playing…")
    play_wav(wav)
    typer.secho("OK: playback finished", fg=typer.colors.GREEN)


@voice_app.command("speak")
def speak(
    text: str = typer.Argument(..., help="Text to synthesize"),
    save: str | None = typer.Option(None, "--save", help="Write WAV to path instead of playing"),
) -> None:
    """TTS only (POST /nexi/voice/speak)."""
    try:
        with _client() as client:
            wav = client.voice_speak(text)
    except Exception as exc:
        _fail(exc)

    if save:
        with open(save, "wb") as f:
            f.write(wav)
        typer.echo(f"Wrote {save}")
        return
    typer.echo(f"Output: {describe_output_device()}")
    play_wav(wav)


@voice_app.command("talk")
def talk(
    once: bool = typer.Option(False, "--once", help="Single utterance then exit"),
    seconds: float = typer.Option(6.0, "--seconds", "-s", help="Record duration per turn"),
    continue_session: bool = typer.Option(
        False,
        "--continue",
        help="Reuse saved CLI session (default: fresh session each launch)",
    ),
    json_out: bool = typer.Option(False, "--json", help="Output raw JSON"),
) -> None:
    """Push-to-talk voice chat loop (record → STT → Nexi → TTS)."""
    try:
        with _client() as client:
            session_id = client._load_session_id() if continue_session else client.new_session()
            if not once:
                typer.echo(
                    "Nexi voice — press Enter to record, /quit to exit "
                    f"(session: {session_id})"
                )
                if not continue_session:
                    typer.echo("Tip: use --continue to keep the saved CLI session.")
            elif not json_out:
                typer.echo(f"Mic: {describe_input_device()}")

            while True:
                if not once:
                    try:
                        user_input = input("\n[Enter] record > ").strip()
                    except (EOFError, KeyboardInterrupt):
                        typer.echo("\nBye.")
                        break
                    if user_input in {"/quit", "/q", "quit", "exit"}:
                        break
                    if user_input.startswith("/text "):
                        msg = user_input.removeprefix("/text ").strip()
                        data = client.chat(msg, session_id=session_id)
                        typer.echo(f"nexi> {data.get('response', '')}")
                        continue

                typer.echo(f"● speak now — recording {seconds:.1f}s…")
                try:
                    pcm = record_seconds(seconds)
                except Exception as exc:
                    _fail(exc)

                _warn_silent_capture(pcm)
                wav = pcm_to_wav_bytes(pcm)

                typer.echo("… transcribing & thinking")
                data = client.voice_chat(wav, session_id=session_id)
                session_id = data.get("session_id", session_id)

                if json_out:
                    typer.echo(json.dumps(data, indent=2))
                else:
                    typer.echo(f"you> {data.get('transcript', '')}")
                    typer.echo(f"nexi> {data.get('response', '')}")

                if not _mute():
                    audio_b64 = data.get("audio_base64")
                    if audio_b64:
                        typer.echo(f"♪ playing reply on {describe_output_device()}…")
                        play_wav(base64.b64decode(audio_b64))

                if once:
                    break
    except typer.Exit:
        raise
    except Exception as exc:
        _fail(exc)
