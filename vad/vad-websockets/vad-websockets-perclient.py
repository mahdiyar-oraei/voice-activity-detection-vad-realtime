"""Realtime per-client VAD over websockets.

Each binary websocket message is one 16 kHz mono s16le audio frame
(20 ms = 320 samples = 640 bytes). For every frame the server replies
with a one-character state:

    1  voice activity in this frame
    _  no voice activity
    X  no voice activity for IDLE_CUT_SECONDS (end-of-utterance marker)

Config via env: VAD_HOST (default 0.0.0.0), VAD_PORT (default 5000),
VAD_MODE (webrtcvad aggressiveness 0-3, default 3).
"""
import asyncio
import os
import sys

import websockets

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from vad_realtime import FrameVAD  # noqa: E402

IDLE_CUT_SECONDS = 0.5

vad = FrameVAD(aggressiveness=int(os.environ.get("VAD_MODE", "3")))


class ClientState:
    """Per-connection silence counter."""

    idle_cut_frames = int(IDLE_CUT_SECONDS / vad.frame_duration)

    def __init__(self):
        self.idle_frames = 0

    def process(self, audio_frame: bytes) -> str:
        if vad.is_speech(audio_frame):
            self.idle_frames = 0
            return "1"
        if self.idle_frames >= self.idle_cut_frames:
            self.idle_frames = 0
            return "X"
        self.idle_frames += 1
        return "_"


async def handler(websocket):
    peer = websocket.remote_address
    print(f"client connected: {peer}")
    state = ClientState()
    try:
        async for message in websocket:
            if not isinstance(message, bytes):
                continue
            await websocket.send(state.process(message))
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        print(f"client disconnected: {peer}")


async def main():
    host = os.environ.get("VAD_HOST", "0.0.0.0")
    port = int(os.environ.get("VAD_PORT", "5000"))
    async with websockets.serve(handler, host, port):
        print(f"VAD websocket server listening on ws://{host}:{port}")
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
