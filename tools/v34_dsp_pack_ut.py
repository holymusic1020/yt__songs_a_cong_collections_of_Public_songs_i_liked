"""UT-34 · 📦 the streaming-delivery pack (Spotify / Apple Music) and its rights gate.

Boss 2026-09-19: "cannot we push this thing… add this with Spotify? or apple music?"
No DSP accepts artist uploads directly — a distributor does. The free, no-card,
AI-friendly route (RouteNote: $0 + 15% of royalties) wants one fixed box per
release, and it makes you CONFIRM commercial rights. So the pack must exist, and
it must refuse any song whose cooking lane can't legally be sold.

Proven:
  1. a commercial-safe lane + a full song → the box is built and zipped
  2. the zip holds audio + 3000×3000 artwork + metadata.json + metadata.md
     (copy-paste sheet) + lyrics.txt + lyrics.lrc + PROVENANCE.md
  3. Suno FREE tier → refused (its own ToS: "cannot be monetized")
  4. MusicGen local → refused (weights are CC-BY-NC)
  5. unknown lane → refused (law: not on the table, doesn't ship)
  6. shorts-only day → nothing to deliver
  7. DSP_PACK=0 → off means off
  8. the boss's own drop → allowed, and the disclosure says it isn't machine-made
"""
import json, os, sys, wave, zipfile
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import dsp_pack, rights

OUT = Path("/tmp/ut34"); (OUT / "dsp").mkdir(parents=True, exist_ok=True)
SR, DUR = 44100, 31
t = np.arange(int(SR * DUR)) / SR
x = np.stack([0.3 * np.sin(2 * np.pi * 220 * t), 0.3 * np.sin(2 * np.pi * 330 * t)],
             axis=1).astype(np.float32)
WAV = OUT / "master.wav"
with wave.open(str(WAV), "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())

COVER = OUT / "cover.png"
from PIL import Image
Image.fromarray((np.random.default_rng(1).integers(0, 255, (900, 1600, 3))).astype("uint8")
                ).save(str(COVER))

META = {"name": "porcelain static — Nix Speech (official audio)", "title": "porcelain static",
        "bpm": 92, "key": "F#m", "lang": "en"}
LRC = [(2.0, "first line"), (5.5, "second line"), (9.0, "third line")]
LYRICS = "first line\nsecond line\nthird line"


def pack(**kw):
    args = dict(wav=WAV, cover=COVER, meta=META, genre_key="lofi", ep=47,
                lane="ace-kaggle", kind="full", lrc_entries=LRC,
                lyrics_text=LYRICS, out_root=OUT, dry_run=True)
    args.update(kw)
    for z in (OUT / "dsp").glob("*.zip"):
        z.unlink()
    return dsp_pack.build_pack(**args)


print("── 1. commercial-safe lane + full song → the box is built")
os.environ.pop("DSP_PACK", None)
r = pack()
assert r["ok"], r
zp = Path(r["zip"]); assert zp.exists() and zp.stat().st_size > 10_000, r
print(f"   ✅ {zp.name} · {r['mb']} MB · lane={r['music_lane']} · release {r['release_date']}")

print("── 2. the zip holds every part a distributor asks for")
names = zipfile.ZipFile(zp).namelist()
need = ["metadata.json", "metadata.md", "PROVENANCE.md", "lyrics.txt", "lyrics.lrc",
        "cover_3000x3000.jpg"]
for part in need:
    assert any(n.endswith(part) for n in names), (part, names)
assert any(n.endswith(".wav") for n in names), names
print(f"   ✅ {len(names)} files: " + ", ".join(sorted(Path(n).name for n in names)))

print("── 3. metadata answers the real form fields")
md = json.loads(zipfile.ZipFile(zp).read([n for n in names if n.endswith("metadata.json")][0]))
for f in ("release_title", "primary_artist", "songwriter", "primary_genre",
          "explicit", "isrc", "upc", "suggested_release_date", "p_line"):
    assert f in md, f
assert md["isrc"] == "" and md["upc"] == "", "the distributor assigns these — never invent them"
assert md["primary_artist"] == "Nix Speech" and md["songwriter"] == "Nix Speech"
assert md["primary_genre"] == "Hip-Hop/Rap" and md["secondary_genre"] == "Lo-Fi"
assert md["explicit"] is False
assert md["audio"]["sample_rate_hz"] == SR and md["audio"]["duration_s"] == 31.0
assert md["ai_disclosure"]["ai_involved"] is True
assert md["ai_disclosure"]["voice_cloning"] is False
assert md["ai_disclosure"]["tools"][0]["license"] == "Apache-2.0"
print(f"   ✅ title='{md['release_title']}' · {md['audio']['format']} "
      f"{md['audio']['sample_rate_hz']}Hz/{md['audio']['bit_depth']}bit/{md['audio']['channels']}")

print("── 4. artwork is a square 3000×3000 JPEG")
art = zipfile.ZipFile(zp).read([n for n in names if n.endswith(".jpg")][0])
im = Image.open(__import__("io").BytesIO(art))
assert im.format == "JPEG" and im.size == (3000, 3000), (im.format, im.size)
print(f"   ✅ {im.size[0]}×{im.size[1]} {im.format} (from a 900×1600 source, padded not stretched)")

print("── 5. lyrics ship plain AND synced")
plain = zipfile.ZipFile(zp).read([n for n in names if n.endswith("lyrics.txt")][0]).decode()
lrc = zipfile.ZipFile(zp).read([n for n in names if n.endswith("lyrics.lrc")][0]).decode()
assert plain.strip() == LYRICS
assert "[00:02.00]first line" in lrc and "[00:09.00]third line" in lrc, lrc
print("   ✅ lyrics.txt + lyrics.lrc (Apple Music timed lyrics)")

print("── 6. provenance names the model, the licence and the link")
prov = zipfile.ZipFile(zp).read([n for n in names if n.endswith("PROVENANCE.md")][0]).decode()
assert "Apache-2.0" in prov and "ACE-Step" in prov and "huggingface.co" in prov
assert "Voice cloning:** none" in prov
print("   ✅ PROVENANCE.md is the receipt RouteNote moderation asks for")

print("── 7. rights gate: the lanes that may NOT be sold")
for lane, why in (("suno", "free tier is non-commercial"),
                  ("musicgen-local", "CC-BY-NC"),
                  ("some-mystery-lane", "not on the table")):
    r = pack(lane=lane, ep=48)
    assert not r["ok"], (lane, r)
    assert not list((OUT / "dsp").glob("*.zip")), f"{lane} produced a pack"
    print(f"   ✅ {lane:16s} refused — {r['why'][:74]}")

print("── 8. shorts-only day → nothing to deliver")
r = pack(kind="short", ep=49)
assert not r["ok"] and "short" in r["why"], r
print(f"   ✅ {r['why']}")

print("── 9. DSP_PACK=0 → off means off")
os.environ["DSP_PACK"] = "0"
r = pack(ep=50)
assert not r["ok"] and "DSP_PACK=0" in r["why"], r
os.environ.pop("DSP_PACK")
print("   ✅ dial respected")

print("── 10. the boss's own drop is his to sell")
assert rights.commercial_safe("human-drop")
r = pack(lane="human-drop", ep=51)
assert r["ok"], r
prov2 = (OUT / "dsp" / "ep051" / "PROVENANCE.md").read_text()
assert "human drop" in prov2 and "Voice cloning:** none" in prov2
print("   ✅ human-drop packs, and the disclosure says it isn't machine-generated")

print("── 11. a broken pack can never break a release")
r = dsp_pack.build_pack(wav=Path("/tmp/ut34/does-not-exist.wav"), meta={}, ep=52,
                        lane="ace-kaggle", kind="full", out_root=OUT)
assert not r["ok"] and "no master wav" in r["why"], r
print(f"   ✅ returns a reason instead of raising: {r['why']}")

print("\nUT-34 PASS · the streaming box is built only from songs we may legally sell")
