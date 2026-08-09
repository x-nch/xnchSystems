"""CLI voice commands — push-to-talk Nexi on gate7."""

from __future__ import annotations

import base64
import json
import os

import typer

from .client import XnchCliClient
from .voice_io import list_devices, pcm_to_wav_bytes, play_wav, record_seconds

voice_app = typer.Typer(help="Voice interaction with Nexi (STT + TTS on gate7).")


def _client() -> XnchCliClient:
    return XnchCliClient()


def _mute() -> bool:
    return os.environ.get("XNCH_VOICE_MUTE", "").lower() in {"1", "true", "yes"}


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

    for dev in devs:
        typer.echo(
            f"[{dev['index']}] {dev['name']} "
            f"(in={dev['max_input_channels']} out={dev['max_output_channels']})"
        )


@voice_app.command("listen")
def listen(
    seconds: float = typer.Option(5.0, "--seconds", "-s", help="Recording duration"),
    json_out: bool = typer.Option(False, "--json", help="Output raw JSON"),
) -> None:
    """Record and transcribe only (POST /nexi/voice/transcribe)."""
    typer.echo(f"Recording {seconds:.1f}s...")
    pcm = record_seconds(seconds)
    wav = pcm_to_wav_bytes(pcm)

    try:
        with _client() as client:
            data = client.voice_transcribe(wav)
    except Exception as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    if json_out:
        typer.echo(json.dumps(data, indent=2))
        return
    typer.echo(data.get("transcript", ""))


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
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    if save:
        with open(save, "wb") as f:
            f.write(wav)
        typer.echo(f"Wrote {save}")
        return
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

                typer.echo(f"● recording {seconds:.1f}s...")
                pcm = record_seconds(seconds)
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
                        typer.echo("♪ playing reply…")
                        play_wav(base64.b64decode(audio_b64))

                if once:
                    break
    except Exception as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
