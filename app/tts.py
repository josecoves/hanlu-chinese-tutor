import asyncio
import hashlib
from pathlib import Path
import edge_tts
from .config import AUDIO_DIR


def audio_name(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:24] + ".mp3"


async def _save(text: str, path: Path):
    await edge_tts.Communicate(text, "zh-CN-XiaoxiaoNeural").save(str(path))


def synthesize(text: str) -> str | None:
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    name = audio_name(text)
    path = AUDIO_DIR / name
    if path.exists():
        return name
    try:
        asyncio.run(_save(text, path))
        return name
    except Exception:
        return None
