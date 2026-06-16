from collections import defaultdict
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

rooms: dict[str, list[WebSocket]] = defaultdict(list)


@router.websocket("/ws/rooms/{token}")
async def room_signaling(websocket: WebSocket, token: str):
    await websocket.accept()
    peers = rooms[token]
    peers.append(websocket)
    try:
        await websocket.send_json({"type": "peers", "count": len(peers)})
        for peer in list(peers):
            if peer is not websocket:
                await peer.send_json({"type": "peer-joined"})
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                continue
            for peer in list(peers):
                if peer is not websocket:
                    await peer.send_json(message)
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in peers:
            peers.remove(websocket)
        for peer in list(peers):
            try:
                await peer.send_json({"type": "peer-left"})
            except Exception:
                pass
        if not peers:
            rooms.pop(token, None)
