"""Copy only the curriculum audio required by the hosted Hanlu build.

Generated clips remain outside the public source repository. The private Sites
artifact includes them at deployment time so playback does not depend on the
browser's speech-synthesis implementation.
"""

import json
import shutil
from pathlib import Path

from app.config import AUDIO_DIR


ROOT = Path(__file__).resolve().parents[1]
CONTENT_PATH = ROOT / "hosted" / "app" / "hanlu-data.json"
OUTPUT_DIR = ROOT / "hosted" / "public" / "audio"


def main() -> None:
    content = json.loads(CONTENT_PATH.read_text(encoding="utf-8"))
    names = {word["audio"] for word in content["words"]}
    names.update(
        sentence["audio"]
        for story in content["stories"]
        for sentence in story["sentences"]
    )
    names.update(
        example["audio"]
        for lesson in content["grammar"]
        for example in lesson["examples"]
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    missing = []
    for name in sorted(names):
        source = AUDIO_DIR / name
        if not source.exists() or source.stat().st_size == 0:
            missing.append(name)
            continue
        destination = OUTPUT_DIR / name
        if not destination.exists() or destination.stat().st_size != source.stat().st_size:
            shutil.copy2(source, destination)

    if missing:
        raise SystemExit(
            f"Missing {len(missing)} required audio clips. Generate them locally first."
        )
    print(f"Prepared {len(names)} hosted audio clips in {OUTPUT_DIR}.")


if __name__ == "__main__":
    main()
