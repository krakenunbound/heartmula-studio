# MiniMax Music 3 Studio — Roadmap

This file tracks planned product work. Confirmed defects and completed repairs remain in `bugslist.md`.

## 1. AI song and prompt assistant

Add an optional AI assistant for turning a plain-language idea into a complete Music 3 request:

- Support a Gemini Flash-class model through a provider adapter, so the exact model can be changed without rewriting the application.
- Keep the API key out of source code, logs, exported projects, and Git. Store it in the operating-system credential store or a local ignored settings file.
- Give the assistant a versioned, human-readable Music 3 authoring guide that explains the required caption structure, supported lyric section tags, vocal assignment strategy, exclusions, duration behavior, and common failure modes.
- Let the user choose among: improve the music description, write lyrics, restructure pasted lyrics, create a complete song, or suggest several distinct directions.
- Always show the proposed description and lyrics before generation. The AI must never silently overwrite the user's text.
- Preserve both the original request and rewritten result in the song's generation history.
- Allow the AI provider to be disabled completely; local music generation must continue to work without internet access.

## 2. Secure LAN browser access — dropped

The sidecar and Tauri host are locked to `127.0.0.1:7784`. Phone/tablet LAN access does not fit this desktop + single-GPU worker setup. Do not implement unless the product becomes a real network service.

## 3. Clear song form — done

Create has **Clear fields**, **Clear description**, and **Clear lyrics**. Confirmation only when the form has meaningful work. Saved library items are not touched.

## 4. Automatic title generation

When Song title is empty or still contains the untouched default:

- Ask the configured AI assistant for a short title based on the lyrics and music description.
- Prefer a memorable phrase or central image from the song rather than a generic genre label.
- Generate the title before the job enters the queue so cards, folders, metadata, artwork prompts, and downloads all use the same name.
- When no AI provider is configured, use a deterministic local fallback derived from meaningful lyric or description phrases.
- Never replace a title the user entered deliberately.

## 5. Generation lineage and A/B listening

Add a visual version tree for every song idea so experimentation is safe and understandable.

- **Reuse as new song** creates a child version linked to its source instead of an unrelated duplicate.
- Record exactly what changed: prompt, lyrics, seed, duration mode, creative latitude, direction strength, and other generation settings.
- Compare two versions side by side with synchronized playback and instant A/B switching at the same timestamp.
- Mark a preferred version and optionally archive rejected experiments without deleting them.
- Let the user restore any earlier version's complete generation recipe with one click.
- Show which cover art, stems, Studio project, exports, and lyric timing belong to each version.

This turns the app into a local song-development workspace rather than a folder of disconnected generations, and makes AI-assisted rewrites from item 1 easy to judge without losing the original.

## 6. Reusable prompt-based voice profiles — done

Create has Prompt voices: Female / Male / Backing slots, a manager for named recipes, compile-off-screen Vocal Details, View compiled prompt, and snapshots saved on each song. Private names are not sent to Music 3.

## Suggested implementation order

1. Generation lineage data model and A/B playback.
2. AI prompt/lyrics/title workflows layered onto the version tree (writing assist already exists).
