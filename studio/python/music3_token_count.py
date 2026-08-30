"""Count HeartMuLa tag and lyric tokens without loading CUDA model weights."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from tokenizers import Tokenizer

# HeartMuLa does not publish a smaller prompt ceiling.  This guard keeps
# accidental pasted documents from creating impractical contexts while leaving
# ample room for song lyrics.
MAX_PROMPT_TOKENS = 8192


def _ids(tokenizer: Tokenizer, value: str, bos: int, eos: int) -> list[int]:
    ids = tokenizer.encode(value).ids
    if not ids or ids[0] != bos:
        ids = [bos, *ids]
    if ids[-1] != eos:
        ids.append(eos)
    return ids


def main() -> int:
    request = json.load(sys.stdin)
    tokenizer = Tokenizer.from_file(str(Path(request["tokenizer"])))
    tags = str(request.get("tags") or "").strip().lower()
    lyrics = str(request.get("lyrics") or "").strip().lower()
    if not tags.startswith("<tag>"):
        tags = f"<tag>{tags}"
    if not tags.endswith("</tag>"):
        tags = f"{tags}</tag>"
    # Pipeline input consists of tags, one continuous-conditioning placeholder,
    # then lyrics.  Account for the placeholder as well as BOS/EOS markers.
    tokens = len(_ids(tokenizer, tags, 128000, 128001)) + 1 + len(_ids(tokenizer, lyrics, 128000, 128001))
    print(json.dumps({"tokens": tokens, "maximum": MAX_PROMPT_TOKENS}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
