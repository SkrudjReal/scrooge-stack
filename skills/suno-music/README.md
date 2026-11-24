# Suno Music Generation — READY TO USE ✅

## Usage

The user simply describes what they want; I automatically:
1. Determine the genre and mood
2. Generate a prompt
3. Create a track
4. Send it to Telegram

## Example requests

**Calm lo-fi:**
> "create a calm evening lo-fi track"
→ `lo-fi, calm and peaceful, soft pads, 75 BPM, high quality`

**Energetic electronic music:**
> "I want energetic electronic music for coding"
→ `electronic, energetic, upbeat, 120 BPM, high quality`

**Slavic folk:**
> "music with Slavic motifs and a choir"
→ `Slavic folk, choir vocals, electronic, 100 BPM, high quality`

**Meditative ambient:**
> "atmospheric music for meditation"
→ `ambient, atmospheric, calm and peaceful, soft pads, 80 BPM`

## Automatic detection

The skill recognizes keywords:
- **Genre:** lo-fi, electronic, Slavic, ambient
- **Mood:** calm, melancholic, energetic
- **BPM:** selected automatically (75-120)

## Technical details

**API:** EvoLink Suno V5
**Timeout:** 6 minutes (in case of a queue)
**Format:** MP3, ~3MB, 2 minutes
**Generation time:** ~1-2 minutes

## Files

- `generate.py` — low-level generation (direct API call)
- `suno.js` — wrapper with automatic prompting
- `.env` — API key (protected)
- `test.py` — test script

## Test

```bash
cd ~/.claude/skills/suno-music   # or ~/.codex/skills/suno-music
python3 generate.py "lo-fi electronic, calm, 75 BPM"
```

## Status: ✅ WORKING

- ✅ Fully functional API
- ✅ Stable generation (~2 minutes)
- ✅ Automatic prompts
- ✅ Telegram delivery
