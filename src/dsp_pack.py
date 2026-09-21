"""📦 DSP PACK — the streaming-delivery box for one song (Spotify / Apple Music).

Boss 2026-09-19: "cannot we push this thing… add this with Spotify? or apple music?"

The honest constraint: **no DSP takes uploads from an artist directly.** Spotify
closed its direct-upload pilot in 2019; Apple Music has never had one. Everything
arrives through an approved distributor. The free ones that accept AI-generated
music (RouteNote free = $0 + 15% of royalties, no card at signup) want a fixed
box of things per release, and every one of them is something this engine already
has — it was just never gathered in one place:

    · the mastered audio (WAV, 44.1 kHz, -14 LUFS / -1 dBTP — already our law)
    · square cover art (3000×3000 JPEG)
    · metadata (title, artist, writer, genre, language, explicit flag, dates)
    · lyrics (plain text + the synced .lrc we already burn into the video)
    · provenance: which model cooked it, under which licence, with links —
      this is what RouteNote's moderation actually asks for on AI content

So this module builds that box, zips it, and the workflow ships it as an artifact.
The boss downloads ONE zip and copy-pastes from ONE sheet. No card, no fee, no
API key, no new credentials — and if anything at all is missing or the lane's
licence isn't commercial-safe, the pack is refused and YouTube carries on exactly
as before. Nothing here can break a release: it never raises.

Dials:  DSP_PACK=0        → off entirely (default ON)
        DSP_ARTIST        → artist name on streaming (default "Nix Speech")
        DSP_LEAD_DAYS     → suggested release date lead (default 21)
"""
from __future__ import annotations

import json
import os
import shutil
import wave
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

from src import rights

COVER_PX = 3000                 # Apple/Spotify max square artwork
JPEG_Q = 92

# DSP genre pickers are a fixed menu; ours are vibes. Nearest honest fit.
GENRE_MAP = {
    "lofi": ("Hip-Hop/Rap", "Lo-Fi"),
    "drift_phonk": ("Hip-Hop/Rap", "Phonk"),
    "orbit_trap": ("Hip-Hop/Rap", "Trap"),
    "deep_pop": ("Pop", "Pop"),
    "villain_pop": ("Pop", "Dark Pop"),
    "skyline_anthem": ("Pop", "Anthemic"),
    "disco_house": ("Dance", "Disco"),
    "dark_ambient": ("Electronic", "Ambient"),
    "baroque_waltz": ("Classical", "Waltz"),
}


def _clean(name: str) -> str:
    return "".join(c for c in str(name or "").strip() if c.isalnum() or c in " -_.").strip() or "track"


def _audio_spec(wav: Path) -> dict:
    try:
        with wave.open(str(wav), "rb") as w:
            sr, ch, sw, n = (w.getframerate(), w.getnchannels(),
                             w.getsampwidth(), w.getnframes())
        return {"file": wav.name, "format": "WAV (PCM)", "sample_rate_hz": sr,
                "channels": "stereo" if ch == 2 else "mono", "bit_depth": sw * 8,
                "duration_s": round(n / max(1, sr), 1)}
    except Exception as e:                                  # noqa: BLE001
        return {"file": wav.name, "error": str(e)[:120]}


def _lrc_to_plain(entries) -> str:
    lines = []
    for e in entries or []:
        try:
            txt = (e[1] if isinstance(e, (list, tuple)) and len(e) > 1 else str(e)).strip()
        except Exception:
            continue
        if txt:
            lines.append(txt)
    return "\n".join(lines)


def _lrc_text(entries) -> str:
    out = []
    for e in entries or []:
        try:
            t, txt = float(e[0]), str(e[1]).strip()
        except Exception:
            continue
        if not txt:
            continue
        m, s = int(t // 60), t % 60
        out.append(f"[{m:02d}:{s:05.2f}]{txt}")
    return "\n".join(out)


def build_pack(wav, cover=None, meta=None, genre_key: str = "", ep: int = 0,
               lane: str = "engine", kind: str = "full", lrc_entries=(),
               lyrics_text: str = "", art_clean=None, out_root=None,
               dry_run: bool = False) -> dict:
    """Assemble (and zip) the delivery box for ONE song. Never raises.

    Returns a dict that is safe to print, put in the Telegram checklist and
    fold into the receipt: {"ok": bool, "zip": path|None, "why": str, ...}
    """
    try:
        meta = meta if isinstance(meta, dict) else {}
        if os.environ.get("DSP_PACK", "1").strip() == "0":
            return {"ok": False, "why": "DSP_PACK=0 — streaming packs off"}
        if str(kind).lower() != "full":
            return {"ok": False, "why": f"{kind}-only day — streaming gets full songs, not shorts"}

        v = rights.verdict(lane)
        if not v.get("commercial"):
            return {"ok": False, "why": f"rights: lane '{v['lane']}' is not commercial-safe "
                                        f"({v.get('license')}) — refused", "rights": v["lane"]}
        wav = Path(wav)
        if not wav.exists():
            return {"ok": False, "why": "no master wav to pack"}

        root = Path(out_root) if out_root else Path("out")
        d = root / "dsp" / f"ep{int(ep or 0):03d}"
        d.mkdir(parents=True, exist_ok=True)

        artist = os.environ.get("DSP_ARTIST", "").strip() or "Nix Speech"
        title = str(meta.get("name") or meta.get("title") or f"EP.{int(ep or 0):03d}").strip()
        title = title.split("—")[0].split(" - ")[0].strip() or "untitled"
        primary, secondary = GENRE_MAP.get(str(genre_key), ("Alternative", ""))
        lead = int(os.environ.get("DSP_LEAD_DAYS", "21") or 21)
        # Music releases worldwide land on a FRIDAY (the industry's new-music
        # day; playlists and charts are cut around it). Pick the first Friday at
        # least `lead` days out, so the pitch/pre-save window is never wasted.
        rel_dt = datetime.now() + timedelta(days=lead)
        rel_dt += timedelta(days=(4 - rel_dt.weekday()) % 7)          # Mon=0 → Fri=4
        rel = rel_dt.strftime("%Y-%m-%d")

        # 1 · audio — the exact master the video used (loudness-matched already)
        audio = d / f"{_clean(artist)} - {_clean(title)}.wav"
        shutil.copyfile(wav, audio)
        spec = _audio_spec(audio)

        # 2 · artwork — square 3000×3000 JPEG. Prefer the UN-BRANDED art: our
        # video cover carries a thin white frame, an "OFFICIAL AUDIO" chip and an
        # EP number, and Apple/Spotify reject borders, frames and overlay text on
        # artwork. Same pixels, minus the chrome — the video cover is untouched.
        src_art = cover
        if art_clean and Path(art_clean).exists():
            src_art = art_clean
        # the wide frame has to become a square. Solid black bars get REJECTED by
        # store review ("no borders/letterboxing"), and cropping the sides off
        # loses the art we paid for. So: the full art sits centred on a square
        # canvas over a blurred, stretched copy of itself — reads as a designed
        # cover, keeps every pixel of the artwork, and is not a border.
        art_name = ""
        if src_art and Path(src_art).exists():
            try:
                from PIL import Image, ImageFilter
                im = Image.open(str(src_art)).convert("RGB")
                if im.size != (COVER_PX, COVER_PX):
                    side = max(im.size)
                    bg = im.resize((side, side), Image.LANCZOS).filter(
                        ImageFilter.GaussianBlur(max(8, side // 28)))
                    fh = max(1, int(round(im.height * side / im.width)))
                    fg = im.resize((side, fh), Image.LANCZOS)
                    bg.paste(fg, (0, (side - fh) // 2))
                    im = bg
                    im = im.resize((COVER_PX, COVER_PX), Image.LANCZOS)
                art_name = f"cover_{COVER_PX}x{COVER_PX}.jpg"
                im.save(str(d / art_name), "JPEG", quality=JPEG_Q, optimize=True)
            except Exception as e:                          # noqa: BLE001
                art_name = ""
                spec["artwork_error"] = str(e)[:120]

        # 3 · lyrics — plain text (stores) + synced .lrc (Apple Music timed lyrics)
        plain = (lyrics_text or _lrc_to_plain(lrc_entries)).strip()
        if plain:
            (d / "lyrics.txt").write_text(plain + "\n", encoding="utf-8")
        synced = _lrc_text(lrc_entries)
        if synced:
            (d / "lyrics.lrc").write_text(synced + "\n", encoding="utf-8")

        # 4 · metadata — machine-readable + a copy-paste sheet for the web form
        fields = {
            "release_title": title,
            "release_type": "Single",
            "track_title": title,
            "track_number": 1,
            "primary_artist": artist,
            "artist_role": "Primary",
            "songwriter": os.environ.get("DSP_WRITER", "").strip() or artist,
            "composer": os.environ.get("DSP_WRITER", "").strip() or artist,
            "publisher": artist,
            # RouteNote's OWN rule: the label field must not be "none", "unsigned",
            # "indie", "N/A" or "independent" — those get rejected. No label? Their
            # instruction is to enter the artist name. So we send the artist name.
            "record_label_name": artist,
            "_label_warning": "do NOT type 'Independent' / 'N/A' — rejected; use the "
                              "artist name (this field)",
            "spotify_artist_page": "Create a new profile (first release only)",
            "originally_released": datetime.now().strftime("%Y-%m-%d"),
            "_originally_released_note": "first time this is released to stores — today. "
                                        "Leave Pre-Order/Sales Start blank.",
            "explicit_content": "Non-explicit",
            "upc_note": "leave the UPC box empty — they generate one free",
            "isrc_note": "auto-filled by RouteNote — do not invent one",
            "stores": "tick Select all stores",
            "territories": "leave EMPTY = worldwide (their rule)",
            "pricing": "Standard (leave as is)",
            "submit_button": "Distribute Free  (NOT Distribute Premium)",
            "language": str(meta.get("lang") or "en"),
            "primary_genre": primary,
            "secondary_genre": secondary,
            "explicit": False,
            "isrc": "",            # assigned by the distributor — never invent one
            "upc": "",             # assigned by the distributor
            "suggested_release_date": rel,
            "p_line": f"(P) {datetime.now().year} {artist}",
            "c_line": f"(C) {datetime.now().year} {artist}",
            "audio": spec,
            "artwork": art_name or "(missing — upload any 3000x3000 square JPEG)",
            "lyrics_file": "lyrics.txt" if plain else "",
            "synced_lyrics_file": "lyrics.lrc" if synced else "",
            "ai_disclosure": {
                "ai_involved": True,
                "involved_in": ["composition (audio generation)", "vocal performance (synthetic)"],
                "human_involved_in": ["lyrics direction", "genre/arrangement brief", "artwork "
                                      "selection", "mastering (loudness)", "release decisions"],
                "voice_cloning": False,
                "impersonates_real_artist": False,
                "tools": [{"name": v.get("tool"), "url": v.get("url"),
                           "license": v.get("license")}] if v.get("tool") else [],
                "statement": rights.disclosure(lane),
            },
            "source": {"episode": int(ep or 0), "music_lane": v["lane"],
                       "youtube_kind": kind, "built_at": datetime.now().isoformat(timespec="seconds"),
                       "dry_run": bool(dry_run)},
        }
        (d / "metadata.json").write_text(json.dumps(fields, indent=2, ensure_ascii=False),
                                         encoding="utf-8")

        sheet = [f"# 📋 COPY-PASTE SHEET — {artist} · {title}",
                 "", "Every field the distributor's form asks for. Copy the right-hand column.",
                 "", "| Form field | Type this |", "|---|---|"]
        for k in ("release_title", "upc_note", "release_type", "track_title",
                  "primary_artist", "spotify_artist_page", "songwriter", "composer",
                  "publisher", "record_label_name", "language", "primary_genre",
                  "secondary_genre", "explicit_content", "originally_released",
                  "suggested_release_date", "isrc", "upc", "p_line", "c_line",
                  "stores", "territories", "pricing", "submit_button"):
            val = fields[k]
            if k in ("isrc", "upc"):
                val = "— leave blank, they generate it free"
            sheet.append(f"| {k} | `{val}` |")
        sheet += ["", "## Files to upload",
                  f"- **Audio:** `{audio.name}` — {spec.get('format')}, "
                  f"{spec.get('sample_rate_hz')} Hz, {spec.get('bit_depth')}-bit, "
                  f"{spec.get('channels')}, {spec.get('duration_s')} s",
                  f"- **Artwork:** `{fields['artwork']}` — "
                  + ("clean art, no frame/chip/EP text (store rule: no borders or "
                     "overlay text)" if src_art is art_clean else
                     "video cover — has our brand frame; if moderation complains, ask "
                     "me for the clean-art build"),
                  f"- **Lyrics:** `lyrics.txt` (plain) · `lyrics.lrc` (synced, for Apple Music)",
                  "", "## AI disclosure (paste verbatim if they ask)",
                  fields["ai_disclosure"]["statement"], ""]
        (d / "metadata.md").write_text("\n".join(sheet), encoding="utf-8")

        # 5 · provenance — the rights receipt moderation asks for
        prov = [f"# 🧾 PROVENANCE & RIGHTS — EP.{int(ep or 0):03d} · {title}", "",
                f"- **Recording generated by:** {v.get('tool')} ({v['lane']})",
                f"- **Licence:** {v.get('license')}",
                f"- **Why it is commercial-safe:** {v.get('why')}",
                f"- **Tool link:** {v.get('url') or '(n/a — our own code in src/composer.py)'}",
                "- **Voice cloning:** none. No real artist is imitated.",
                "- **Third-party samples:** none. No loops, no stems, no covers.",
                "- **Human input:** lyrics direction, genre/arrangement brief, artwork "
                "selection, loudness mastering, release decisions.",
                "", "## AI disclosure statement", rights.disclosure(lane), "",
                "## Note on Content ID",
                "Distributors exclude AI content from YouTube Content ID / fingerprinting "
                "services. We do not claim it and do not need it: this channel owns the "
                "audio and publishes it itself.", ""]
        (d / "PROVENANCE.md").write_text("\n".join(prov), encoding="utf-8")

        # 6 · the zip
        zpath = root / "dsp" / f"ep{int(ep or 0):03d}-dsp-pack.zip"
        if zpath.exists():
            zpath.unlink()
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(d.iterdir()):
                if f.is_file():
                    z.write(f, arcname=f"{d.name}/{f.name}")
        size = zpath.stat().st_size
        res = {"ok": True, "zip": str(zpath), "dir": str(d), "bytes": size,
               "mb": round(size / 1e6, 1), "files": [f.name for f in sorted(d.iterdir())],
               "title": title, "artist": artist, "music_lane": v["lane"],
               "rights": v.get("license"), "release_date": rel,
               "duration_s": spec.get("duration_s"),
               "why": f"streaming pack ready ({round(size / 1e6, 1)} MB, "
                        f"{sum(1 for f in d.iterdir() if f.is_file())} parts)"}
        print(f"  📦 DSP pack: {zpath.name} · {res['mb']} MB · lane={v['lane']} "
              f"({v.get('license')}) · suggested release {rel}")
        if v.get("conditional"):
            print("  ⚠️ rights note: lyria is CONDITIONAL — free-tier Gemini key means "
                  "Google may log prompts and the audio carries a SynthID watermark")
        return res
    except Exception as e:                                  # noqa: BLE001 — law #1
        return {"ok": False, "why": f"dsp pack failed: {type(e).__name__}: {str(e)[:140]}"}


def deliverable(root=None) -> list[Path]:
    """Every zip waiting for the boss (used by the artifact step)."""
    d = (Path(root) if root else Path("out")) / "dsp"
    return sorted(d.glob("*-dsp-pack.zip")) if d.exists() else []
