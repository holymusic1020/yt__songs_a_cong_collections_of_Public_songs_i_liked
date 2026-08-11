"""v22 receipt: 9-genre universe — coverage guard + render smoke.

Guard doctrine: a genre that exists in the composer but is missing from ANY
genre-keyed dict (tags/names/hashtags/lyrics/scenes/prompts/styles) is a
runner crash waiting for Tuesday. Assert the full matrix here, once.
"""
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import art_gemini, composer, lyrics, metadata, music_space, music_suno  # noqa: E402
import src.main as mainmod                                                    # noqa: E402

EXPECT = sorted(composer.GENRES)


def guard_matrix():
    print("== coverage matrix: 9 genres x every genre-keyed dict ==")
    dicts = {
        "metadata.TAGS": metadata.TAGS,
        "metadata.NAME_BANKS": metadata.NAME_BANKS,
        "metadata.HASHTAGS": metadata.HASHTAGS,
        "lyrics.LINES": lyrics.LINES,
        "art_gemini.SCENE_VARIANTS": art_gemini.SCENE_VARIANTS,
        "music_space.PROMPTS": music_space.PROMPTS,
        "music_space.GENRE_BPM": music_space.GENRE_BPM,
        "music_space.VOICE": music_space.VOICE,
        "music_suno.STYLES": music_suno.STYLES,
        "music_suno.GENRE_BPM": music_suno.GENRE_BPM,
        "music_suno.VOCAL_GENDER": music_suno.VOCAL_GENDER,
    }
    missing = [(g, name) for name, d in dicts.items() for g in EXPECT
               if g not in d]
    assert not missing, f"MISSING ENTRIES: {missing}"
    rot = mainmod.GENRE_ROTATION
    assert sorted(rot) == EXPECT, f"rotation mismatch: {rot}"
    # prompts must survive .format(bpm=...); new ones display the bpm
    for g in EXPECT:
        pr = music_space.build_prompt(g, "en", True)
        assert len(pr) > 20
        st = music_suno.STYLES[g]
        assert 10 < len(st) < 1000
    for g in ("skyline_anthem", "villain_pop", "orbit_trap"):
        assert "{bpm}" not in music_space.build_prompt(g, "en", True)
    print(f"  ✓ {len(EXPECT)} genres x {len(dicts)} dicts: full coverage")
    print(f"  ✓ rotation spans all {len(rot)} genres")


def smoke_compose():
    print("\n== compose smoke: every genre, plus deep-check the 3 new engines ==")
    for g in EXPECT:
        rng = np.random.default_rng(101)
        t0 = time.time()
        x, info = composer.compose(g, rng, 24.0)
        x = composer.arrange_arc(x, info["bpm"])
        peak = float(np.max(np.abs(x)))
        dur = len(x) / 44100
        assert 0.2 < peak <= 1.0, (g, peak)
        assert dur > 20, (g, dur)
        ev = info.get("events", {})
        print(f"  ✓ {g:<16} {dur:5.1f}s  peak {peak:.2f}  "
              f"{time.time()-t0:4.1f}s  events={ev or '—'}")
    for g in ("skyline_anthem", "villain_pop", "orbit_trap"):
        rng = np.random.default_rng(7)
        x, info = composer.compose(g, rng, 150.0)      # full-length truth
        ev = info["events"]
        assert ev["risers"] >= 3 and ev["rolls"] >= 3 and ev["crashes"] >= 3, ev
        print(f"  ✓ {g:<16} full-length: {ev['risers']} risers / "
              f"{ev['rolls']} rolls / {ev['crashes']} crashes  "
              f"({info['bpm']} bpm, {info['key']})")


def meta_integration():
    print("\n== metadata + lyric cards for the new genres ==")
    import random
    for g in ("skyline_anthem", "villain_pop", "orbit_trap"):
        rng_py = random.Random(5)
        info = {"bpm": 130, "key": "A minor", "genre": g, "duration_s": 60}
        meta = metadata.build(g, info, 42, rng_py, used_names=set(),
                              name="midnight test", lang="en", vocal=True)
        assert meta["title"] and meta["description"] and meta["tags"]
        lines = lyrics.build_lines(g, meta["name"], rng_py, n=5)
        assert len(lines) >= 3 and all(len(l) > 5 for l in lines)
        sung = lyrics.song_lyrics(g, meta["name"], rng_py, "en")
        assert "[chorus]" in sung
        print(f"  ✓ {g:<16} title={meta['title']!r}  card1={lines[0]!r}")


if __name__ == "__main__":
    guard_matrix()
    smoke_compose()
    meta_integration()
    print("\nALL GREEN ✓ — the universe has 9 vibes now")
