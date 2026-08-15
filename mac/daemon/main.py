"""XNCH command center daemon — capture → gate7 voice chat → WS broadcast."""

from __future__ import annotations

import base64
import threading
import time

from .audio import capture_loop, pcm_to_wav_bytes, play_wav
from .bridge import broadcast, start_bridge
from .config import DaemonConfig
from .gateway import GatewayClient
from .segmenter import VadSegmenter, is_garbage


class Daemon:
    def __init__(self, config: DaemonConfig | None = None) -> None:
        self.config = config or DaemonConfig.from_env()
        self.gateway = GatewayClient(self.config)
        self.segmenter = VadSegmenter(sample_rate=self.config.sample_rate)
        self._session_id: str | None = None
        self._armed = False
        self._last_transcript = ""

    # --- WS command dispatch -------------------------------------------
    def handle_command(self, cmd: dict) -> None:
        cmd_type = cmd.get("type")
        if cmd_type == "arm":
            self.arm()
        elif cmd_type == "disarm":
            self.disarm()
        elif cmd_type == "health":
            self._broadcast_health()

    # --- push-to-talk ------------------------------------------------
    def arm(self) -> None:
        if self._armed:
            return
        self._armed = True
        self.segmenter.set_armed(True)
        broadcast({"type": "status", "text": "Listening…"})

    def disarm(self) -> None:
        if not self._armed:
            return
        self._armed = False
        self.segmenter.set_armed(False)
        segment = self.segmenter.flush()
        if segment is not None:
            threading.Thread(target=self._handle_segment, args=(segment,), daemon=True).start()

    # --- segment handling --------------------------------------------
    def _handle_segment(self, segment: bytes) -> None:
        wav = pcm_to_wav_bytes(segment, sample_rate=self.config.sample_rate)
        broadcast({"type": "status", "text": "Thinking…"})
        try:
            data = self.gateway.voice_chat(wav, session_id=self._session_id, return_audio=True)
        except Exception as exc:
            broadcast({"type": "status", "text": f"gate7 error: {exc}"})
            return

        transcript = data.get("transcript", "")
        if not transcript or is_garbage(transcript) or transcript == self._last_transcript:
            broadcast({"type": "status", "text": "No new input detected"})
            return
        self._last_transcript = transcript
        self._session_id = data.get("session_id", self._session_id)

        broadcast({
            "type": "voice_result",
            "transcript": transcript,
            "response": data.get("response", ""),
            "session_id": self._session_id,
        })
        audio_b64 = data.get("audio_base64")
        if audio_b64:
            threading.Thread(
                target=play_wav,
                args=(base64.b64decode(audio_b64),),
                kwargs={"device": self.config.output_device},
                daemon=True,
            ).start()

    # --- cluster health ------------------------------------------------
    def _probe_health(self) -> dict:
        result = {"xnch": "down", "nexi": "down", "media": "down"}
        probes = {
            "xnch": lambda: self.gateway.health(),
            "nexi": lambda: self.gateway.nexi_health(),
            "media": lambda: self.gateway.media_health(),
        }
        for name, probe in probes.items():
            try:
                status = probe().get("status")
                result[name] = "ok" if status == "ok" else "err"
            except Exception:
                pass
        return result

    def _broadcast_health(self) -> None:
        broadcast({"type": "health", "health": self._probe_health()})

    def health_loop(self) -> None:
        while True:
            self._broadcast_health()
            time.sleep(10)

    # --- lifecycle -----------------------------------------------------
    def run(self) -> None:
        start_bridge(on_command=self.handle_command,
                     host=self.config.ws_host,
                     ws_port=self.config.ws_port,
                     http_port=self.config.http_port)
        threading.Thread(target=self.health_loop, daemon=True).start()
        broadcast({"type": "status", "text": f"XNCH command center — {self.config.base_url}"})

        try:
            from pynput import keyboard

            listener = keyboard.Listener(on_press=self._hotkey_press,
                                         on_release=self._hotkey_release)
            listener.start()
        except Exception as exc:
            print(f"[cc] hotkey disabled: {exc}")

        capture_loop(self.segmenter, self.config, self._on_capture_segment)

    def _on_capture_segment(self, segment: bytes) -> None:
        threading.Thread(target=self._handle_segment, args=(segment,), daemon=True).start()

    def _hotkey_press(self, key) -> None:
        from pynput import keyboard

        if key == keyboard.Key.caps_lock:
            self.arm()

    def _hotkey_release(self, key) -> None:
        from pynput import keyboard

        if key == keyboard.Key.caps_lock:
            self.disarm()


def main() -> None:
    Daemon().run()


if __name__ == "__main__":
    main()
