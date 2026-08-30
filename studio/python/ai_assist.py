"""Cloud assist. Every call attaches the job's how-to pack; a key alone is not a prompt."""
from __future__ import annotations

import json
import logging
import re
import time
import urllib.error
import urllib.request
from typing import Any, Literal

import ai_guides
import ai_vault
import caption_library

log = logging.getLogger("music3.assist")

ENDPOINTS = {
    "gemini": "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
    "xai": "https://api.x.ai/v1/chat/completions",
    "groq": "https://api.groq.com/openai/v1/chat/completions",
    "openai": "https://api.openai.com/v1/chat/completions",
    "anthropic": "https://api.anthropic.com/v1/messages",
    "nvidia": "https://integrate.api.nvidia.com/v1/chat/completions",
}


def prepare(
    capability: str,
    orientation: Literal["landscape", "portrait"] = "landscape",
    guide_name: str | None = None,
) -> dict[str, Any]:
    """Refuse unless Enable is on, then bind the matching instruction pack.

    `guide_name` lets one vault capability drive more than one prompt pack —
    lyrics and structured captions are both "writing" as far as keys and
    provider settings go, but they need very different instructions.
    """
    access = ai_vault.require_enabled(capability)
    guide = ai_guides.pack(guide_name or capability, orientation=orientation)
    return {
        "provider": access["provider"],
        "model": access["model"],
        "key": access["key"],
        "system": guide["system"],
        "constraints": guide["constraints"],
        "orientation": guide.get("orientation"),
    }


def write(action: str, *, idea: str = "", random: bool = False, title: str = "", description: str = "", lyrics: str = "", language: str = "en") -> dict[str, str]:
    if action not in {"generate", "optimize", "title"}:
        raise ValueError("Unknown writing action")
    packed = prepare("writing")
    user = _writing_user(action, idea=idea, random=random, title=title, description=description, lyrics=lyrics, language=language)
    raw = _complete(packed["provider"], packed["model"], packed["key"], packed["system"], user, temperature=0.95, label="lyrics")
    parsed = _parse_writing(raw)
    out_lyrics = str(parsed.get("lyrics") or "").strip()
    out_title = str(parsed.get("title") or "").strip()
    if action == "title" and not out_title:
        out_title = _first_title_line(out_lyrics or raw)
        out_lyrics = ""
    if action != "title" and _looks_like_json_junk(out_lyrics):
        raise RuntimeError("The writing model returned raw JSON instead of lyrics. Try Generate again.")
    if action != "title" and not out_lyrics:
        raise RuntimeError("The writing model returned empty lyrics")
    if action == "title" and not out_title:
        raise RuntimeError("The writing model returned an empty title")
    if action == "title":
        out_title = re.sub(r"\s+", " ", out_title).strip(" .\"'")[:120]
    return {"lyrics": out_lyrics, "title": out_title, "description": str(parsed.get("description") or "").strip()}


def _writing_user(action: str, **fields: Any) -> str:
    language = fields.get("language") or "en"
    title = str(fields.get("title") or "").strip()
    description = str(fields.get("description") or "").strip()
    lyrics = str(fields.get("lyrics") or "").strip()
    idea = str(fields.get("idea") or "").strip()
    if action == "optimize":
        task = "Rewrite and structure the current lyrics for HeartMuLa. Keep the meaning. Fix official section tags. Tighten repeats. Do not paste the same verses back."
    elif action == "title":
        task = "Propose one short song title from the lyrics and description. Prefer a memorable phrase or central image. Do not copy a chorus line, first verse, or a generic genre label."
    elif fields.get("random"):
        task = "Write a complete original lyric from the music description and title. Invent a specific story. Do not reuse stock AI-lyric clichés."
    elif idea:
        task = f"Write a complete original lyric from this idea:\n{idea}"
    else:
        task = "Write a complete original lyric from the title and music description."
    if action == "title":
        return (
            f"{task}\n\n"
            f"Language: {language}\n"
            f"Current title: {title or '(empty)'}\n"
            f"Music description:\n{description or '(none)'}\n\n"
            f"Current lyrics:\n{lyrics or '(empty)'}\n\n"
            "Reply with one line only, in this exact shape: Title: Your Title Here\n"
            "No lyrics, JSON, markdown, or extra commentary."
        )
    return (
        f"{task}\n\n"
        f"Language: {language}\n"
        f"Current title: {title or '(empty)'}\n"
        f"Music description:\n{description or '(none)'}\n\n"
        f"Current lyrics:\n{lyrics or '(empty)'}\n\n"
        "Reply in plain text only. First line may be Title: a short title. "
        "Then ONLY the sung lyric stream, starting with an official section tag such as [Verse]. "
        "Do not write Global Metadata, Vocal Details, Arrangement, production notes, or bullet lists in the lyrics. "
        "Those belong in the Music Description field, not the lyric stream. "
        "Do not wrap the answer in JSON, braces, or markdown fences."
    )


def describe(*, description: str = "", title: str = "", lyrics: str = "", idea: str = "", language: str = "en") -> dict[str, str]:
    """Expand a rough idea into a HeartMuLa-ready structured description.

    This is the input that actually steers the audio. It runs on the same vault
    entry as lyrics (same key, same provider) but on the description prompt pack,
    with real reference captions retrieved locally from the bundled library.
    """
    packed = prepare("writing", guide_name="caption")
    # A typed idea is the whole brief. Mixing it with whatever the prompt-helper
    # fields happen to still hold is how "cyberpunk zebras" comes back as a
    # generic alto folk ballad.
    brief = (idea or "").strip() or (description or "").strip()
    if not brief and not title and not lyrics:
        raise ValueError("Describe needs a music description, a title, or lyrics to work from")

    references = caption_library.reference_block(brief, lyrics=lyrics, title=title)
    user = _caption_user(brief=brief, title=title, lyrics=lyrics, language=language, references=references)
    # Captions are a structured design task, not a creative-writing task. Lower
    # temperature keeps the sub-fields disciplined.
    raw = _complete(packed["provider"], packed["model"], packed["key"], packed["system"], user, temperature=0.6, label="caption")
    caption = _clean_caption(raw)
    missing = [heading for heading in ai_guides.CAPTION_HEADINGS if not _has_heading(caption, heading)]
    if missing:
        raise RuntimeError(
            "The writing model returned a caption without " + ", ".join(missing)
            + ". Try Describe again, or switch the writing model in API Keys."
        )
    return {"description": caption, "references": _reference_labels(brief, lyrics, title)}


CHAT_HISTORY_LIMIT = 24
_BRIEF_SPLIT = re.compile(r"(?im)^[ \t]*-{2,}\s*BRIEF\s*-{2,}[ \t]*$")


def chat(messages: list[dict[str, str]], *, language: str = "en", instrumental: bool = False) -> dict[str, Any]:
    """Easy mode's co-producer turn.

    Returns the conversational reply the user sees, plus the hidden brief that
    drives caption writing. `ready` is False only when the model decided it had
    to ask something first.
    """
    history = [
        {"role": "assistant" if str(item.get("role")) == "assistant" else "user",
         "content": str(item.get("content") or "").strip()}
        for item in (messages or [])
        if str(item.get("content") or "").strip()
    ][-CHAT_HISTORY_LIMIT:]
    if not history or history[-1]["role"] != "user":
        raise ValueError("The last message must come from the user")

    packed = prepare("writing", guide_name="chat")
    raw = _complete(
        packed["provider"], packed["model"], packed["key"], packed["system"],
        _chat_user(history, language=language, instrumental=instrumental),
        temperature=0.85, effort="LOW", timeout=45, label="chat",
    )
    reply, brief = _split_brief(raw)
    if not reply and not brief:
        raise RuntimeError("The writing model returned an empty reply. Try again.")
    if not reply:
        # A brief with no chat line still beats showing the user nothing.
        reply = "On it — here's what I'm making."
    return {"reply": reply, "brief": brief, "ready": bool(brief)}


def _chat_user(history: list[dict[str, str]], *, language: str, instrumental: bool) -> str:
    lines = ["Conversation so far:", ""]
    for item in history:
        speaker = "User" if item["role"] == "user" else "You"
        lines.append(f"{speaker}: {item['content']}")
    lines += ["", f"Lyrics language: {language}"]
    if instrumental:
        lines.append("The user has the Instrumental switch ON. Plan an instrumental track with no vocals.")
    lines += ["", "Reply to the user's latest message now, following the output contract."]
    return "\n".join(lines)


def _split_brief(raw: str) -> tuple[str, str]:
    text = _clean_caption(raw)
    parts = _BRIEF_SPLIT.split(text, maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    # Some models drop the rule to its own line; fall back to an inline marker.
    marker = text.find(ai_guides.BRIEF_MARKER)
    if marker >= 0:
        return text[:marker].strip(), text[marker + len(ai_guides.BRIEF_MARKER):].strip()
    return text.strip(), ""


def compose(*, idea: str = "", title: str = "", language: str = "en", instrumental: bool = False) -> dict[str, str]:
    """One line in, a whole song brief out.

    This is the front door: "a cyberpunk song about juggling zebras" becomes a
    title, a structured description that becomes comma-separated HeartMuLa tags, and a tagged lyric stream. The
    caption is written first so the lyrics are written to fit the music rather
    than the other way round.
    """
    seed = (idea or title).strip()
    if not seed:
        raise ValueError("Give me a song idea to work from")

    caption_result = describe(idea=seed, title=title, language=language)
    caption = caption_result["description"]

    if instrumental:
        out_title = title.strip()
        if not out_title:
            try:
                out_title = write("title", title=title, description=caption, language=language).get("title", "")
            except Exception:
                log.exception("Auto-title for instrumental compose failed")
        return {"title": out_title, "description": caption, "lyrics": "",
                "references": caption_result.get("references", "")}

    written = write("generate", idea=seed, title=title, description=caption, language=language)
    out_title = (written.get("title") or title).strip()
    if not out_title:
        try:
            out_title = write("title", title=title, description=caption,
                              lyrics=written.get("lyrics", ""), language=language).get("title", "")
        except Exception:
            log.exception("Auto-title after compose failed")
            out_title = ""
    return {
        "title": out_title,
        "description": caption,
        "lyrics": written.get("lyrics", ""),
        "references": caption_result.get("references", ""),
    }


def _caption_user(*, brief: str, title: str, lyrics: str, language: str, references: str) -> str:
    tagged = _section_tags_in(lyrics)
    parts = [
        "Write one HeartMuLa-ready structured description for this song.",
        "",
        f"Language: {language}",
        f"Title (context only, never print it): {title or '(untitled)'}",
        "",
        "The user's brief:",
        brief or "(none given - infer a conservative, coherent treatment)",
    ]
    if tagged:
        parts += ["", "Section tags present in the lyrics, in order: " + " ".join(tagged),
                  "Build the Arrangement timeline around exactly these sections."]
    elif lyrics.strip():
        parts += ["", "The lyrics carry no section tags. Choose a section order that suits the style."]
    if references:
        parts += ["", references]
    parts += [
        "",
        "Return only the caption: the three headings, their official sub-fields, and nothing else.",
        "No title, no lyrics, no markdown, no JSON, no preamble.",
    ]
    return "\n".join(parts)


_TAG_RE = re.compile(r"\[(Intro|Verse|Prechorus|Chorus|Post-Chorus|Bridge|Instrumental|Solo|Outro)\]", re.I)


def _section_tags_in(lyrics: str) -> list[str]:
    seen = [f"[{match.group(1)}]" for match in _TAG_RE.finditer(lyrics or "")]
    return seen[:24]


def _has_heading(caption: str, heading: str) -> bool:
    return re.search(rf"(?im)^\s*{re.escape(heading)}\s*:?\s*$", caption) is not None


def _clean_caption(raw: str) -> str:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()
    # Models like to decorate the headings. Keep the studio description headings bare.
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    text = re.sub(r"(?m)^\s*\*\*(.+?)\*\*\s*:?\s*$", r"\1", text)
    text = text.replace("**", "")
    text = re.sub(r"(?m)^\s*[-*]\s+", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _reference_labels(brief: str, lyrics: str, title: str) -> str:
    """Human-readable note about which library references were consulted."""
    try:
        picked = caption_library.select(brief, lyrics=lyrics, title=title)
    except Exception:
        return ""
    return ", ".join(f"{card['role']}: {card['style']}" for card in picked)


def _complete(provider: str, model: str, key: str, system: str, user: str, *, temperature: float = 0.95,
              effort: str = "MEDIUM", timeout: int = 90, label: str = "writing") -> str:
    started = time.monotonic()
    try:
        return _complete_inner(provider, model, key, system, user,
                               temperature=temperature, effort=effort, timeout=timeout)
    finally:
        # Timed so a "the app froze" report can be checked against what the
        # cloud call actually cost. Shows up in the Logs panel at INFO.
        log.info("assist %s via %s/%s took %.1fs", label, provider, model, time.monotonic() - started)


def _complete_inner(provider: str, model: str, key: str, system: str, user: str, *, temperature: float = 0.95,
                    effort: str = "MEDIUM", timeout: int = 90) -> str:
    if provider == "gemini":
        return _gemini(model, key, system, user, temperature=temperature, effort=effort, timeout=timeout)
    if provider == "anthropic":
        return _anthropic(model, key, system, user, temperature=temperature, timeout=timeout)
    if provider in {"xai", "groq", "openai", "nvidia"}:
        return _openai_compat(provider, model, key, system, user, temperature=temperature, timeout=timeout)
    raise ValueError(f"Writing is not wired for {provider}")


def _gemini(model: str, key: str, system: str, user: str, *, temperature: float = 0.95,
            effort: str = "MEDIUM", timeout: int = 90) -> str:
    url = ENDPOINTS["gemini"].format(model=model or "gemini-3.5-flash")
    # Songwriting and caption design are reasoning tasks. Earlier builds sent
    # thinkingLevel MINIMAL / thinkingBudget 0 at high temperature, which is the
    # fastest way to get generic, cliche output. Ask for real thinking first and
    # only degrade if the model rejects the field.
    configs = (
        {"temperature": temperature, "maxOutputTokens": 8192, "thinkingConfig": {"thinkingLevel": effort}},
        {"temperature": temperature, "maxOutputTokens": 8192, "thinkingConfig": {"thinkingLevel": "LOW"}},
        {"temperature": temperature, "maxOutputTokens": 8192},
    )
    last_error: Exception | None = None
    for config in configs:
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": config,
        }
        request = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-goog-api-key": key},
            method="POST",
        )
        try:
            body = _http(request, timeout=timeout)
            parts = body["candidates"][0]["content"]["parts"]
            return "".join(str(part.get("text") or "") for part in parts if not part.get("thought"))
        except RuntimeError as error:
            last_error = error
            if "HTTP 400" not in str(error):
                raise
        except (KeyError, IndexError, TypeError) as error:
            raise RuntimeError("Gemini returned an unexpected response") from error
    raise RuntimeError(str(last_error) if last_error else "Gemini request failed")


def _openai_compat(provider: str, model: str, key: str, system: str, user: str, *, temperature: float = 0.95,
                   timeout: int = 90) -> str:
    defaults = {
        "xai": "grok-3",
        "groq": "llama-3.3-70b-versatile",
        "openai": "gpt-4.1-mini",
        "nvidia": "minimaxai/minimax-m3",
    }
    payload = {
        "model": model or defaults[provider],
        "temperature": temperature,
        "max_tokens": 4096,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    request = urllib.request.Request(
        ENDPOINTS[provider], data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )
    body = _http(request, timeout=timeout)
    try:
        return str(body["choices"][0]["message"]["content"] or "")
    except (KeyError, IndexError, TypeError) as error:
        raise RuntimeError(f"{provider} returned an unexpected response") from error


def _anthropic(model: str, key: str, system: str, user: str, *, temperature: float = 0.95,
               timeout: int = 90) -> str:
    payload = {
        "model": model or "claude-sonnet-4-5",
        "max_tokens": 4000,
        "temperature": min(temperature, 1.0),
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    request = urllib.request.Request(
        ENDPOINTS["anthropic"], data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01"},
        method="POST",
    )
    body = _http(request, timeout=timeout)
    try:
        return "".join(str(block.get("text") or "") for block in body.get("content") or [] if block.get("type") == "text")
    except TypeError as error:
        raise RuntimeError("Anthropic returned an unexpected response") from error


def _http(request: urllib.request.Request, *, timeout: int = 90) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"Writing provider HTTP {error.code}: {detail}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Could not reach the writing provider ({error.reason})") from error
    try:
        return json.loads(raw)
    except json.JSONDecodeError as error:
        raise RuntimeError("Writing provider did not return JSON") from error


def _first_title_line(text: str) -> str:
    line = (text or "").strip().splitlines()[0] if (text or "").strip() else ""
    line = re.sub(r'(?is)^(?:```\w*\s*)?(?:\{\s*)?(?:"title"\s*:\s*")?', "", line)
    line = re.sub(r'(?i)^title\s*:\s*', "", line)
    return line.strip().strip('",.}{ ').strip()


def _looks_like_json_junk(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if stripped in {"{", "}", "{}", "[", "]"}:
        return True
    if re.match(r'^[{\s]*"(?:title|lyrics)"\s*:', stripped):
        return True
    return stripped.startswith("{") and "[Verse]" not in stripped and "[Chorus]" not in stripped and "[Intro]" not in stripped


def _unescape_json_string(value: str) -> str:
    try:
        return json.loads(f'"{value}"')
    except json.JSONDecodeError:
        return value.replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"').replace("\\\\", "\\")


def _field(text: str, name: str) -> str:
    quoted = re.search(rf'"{name}"\s*:\s*"((?:\\.|[^"\\])*)"', text, re.S)
    if quoted:
        return _unescape_json_string(quoted.group(1)).strip()
    block = re.search(rf'"{name}"\s*:\s*"""([\s\S]*?)"""', text)
    if block:
        return block.group(1).strip()
    return ""


def _parse_writing(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json|text)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()
    parsed = _parse_json(text)
    lyrics = str(parsed.get("lyrics") or "").strip() or _field(text, "lyrics")
    title = str(parsed.get("title") or "").strip() or _field(text, "title")
    if not lyrics and not title:
        title_match = re.match(r"(?i)^title\s*:\s*(.+)\n+([\s\S]+)$", text)
        if title_match:
            title = title_match.group(1).strip().strip('"')
            lyrics = title_match.group(2).strip()
        else:
            lyrics = text
    description, lyrics = _split_caption_and_lyrics(lyrics)
    return {"lyrics": lyrics, "title": title, "description": description}


SECTION_LINE = re.compile(
    r"(?im)^\s*\[(?:Intro|Verse|Prechorus|Chorus|Post-Chorus|Bridge|Instrumental|Solo|Outro)\]\s*$"
)


def _split_caption_and_lyrics(text: str) -> tuple[str, str]:
    body = (text or "").strip()
    if not body:
        return "", ""
    match = SECTION_LINE.search(body)
    if not match:
        if re.search(r"(?im)^(?:#{1,6}\s*)?Global Metadata\b", body):
            return body, ""
        return "", body
    before = body[: match.start()].strip()
    after = body[match.start():].strip()
    if re.search(r"(?im)Global Metadata|Vocal Details|^Arrangement\b", before):
        return before, after
    return "", body


def _parse_json(raw: str) -> dict[str, Any]:
    text = raw.strip().lstrip("\ufeff")
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()
    candidates = [text]
    if not text.startswith("{"):
        candidates.append("{" + text)
    for candidate in list(candidates):
        trimmed = candidate.rstrip()
        while trimmed.endswith("}") and trimmed.count("}") > trimmed.count("{"):
            extra = trimmed[:-1].rstrip()
            candidates.append(extra)
            trimmed = extra
        if not trimmed.endswith("}"):
            candidates.append(trimmed + "}")
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue
    match = re.search(r"\{.*\}", text, re.S)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    lyrics, title = _field(text, "lyrics"), _field(text, "title")
    if lyrics or title:
        return {"lyrics": lyrics, "title": title}
    return {}
