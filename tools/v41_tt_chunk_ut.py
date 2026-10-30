#!/usr/bin/env python3
"""UT-41 · TikTok chunk arithmetic (the lane that silently died for 3 days).

EP.065, EP.066 and EP.067 all came back `400 invalid_params · The chunk size is
invalid` — the draft the boss publishes by hand simply stopped existing, and the
run stayed green because the lane is isolated by design. Cause: chunk_size was
`min(size, 10 MB)`, legal only when the mp4 size happened to be a multiple of 8.
"""
import io, json, os, sys, urllib.request
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
ok = bad = 0
def chk(c, l, x=""):
    global ok, bad
    if c: ok += 1; print(f"  ✅ {l}")
    else: bad += 1; print(f"  ❌ {l}" + (f" — {x}" if x else ""))

from src import multi_post
from src.multi_post import tt_chunks

# TikTok's OWN doc example: video_size 50,000,123 with chunk_size 10,000,000 →
# total_chunk_count 5 (floor), last chunk oversized at 10,000,123 bytes.
chk(tt_chunks(4_000_000) == (4_000_000, 1), "aligned file → 1 chunk (the case that always worked)")
cs, n = tt_chunks(5_000_003)
chk(cs % 8 == 0 and n == 2 and cs * 2 <= 5_000_003 < cs * (n + 1),
    f"odd size → {cs} × {n}: split, so the remainder rides in an oversized tail "
    f"(a lone chunk would have to claim chunk_size ≠ video_size → EP.079/080's 400)",
    f"{cs},{n}")
chk(tt_chunks(50_000_123, cap=10_000_000) == (10_000_000, 5),
    "TikTok's documented example reproduced exactly: 50,000,123 / 10,000,000 → 5 chunks")
for size in (16, 17, 24, 25, 655_357, 4_000_000, 1_000_003, 5_000_003,
             64 * 1024 * 1024 - 1, 64 * 1024 * 1024, 64 * 1024 * 1024 + 1,
             67_108_865, 130_000_000, 137_423_105,
             500_000_001, 1_073_741_824, 4_999_999, 5_000_001):
    c, k = tt_chunks(size)
    assert c % 8 == 0, ("chunk not /8", size, c)
    assert c <= max(size, 8), ("chunk bigger than file", size, c)
    assert c <= 64 * 1024 * 1024, ("chunk over the 64 MB ceiling", size, c)
    assert c * k <= size + c, ("plan needs more bytes than the file has", size, c, k)
    assert k == max(1, size // c), ("count != floor(size/chunk)", size, c, k)
    last = size - (k - 1) * c
    assert 0 < last <= 2 * c, ("tail chunk out of contract", size, c, k, last)
    assert last <= 128 * 1024 * 1024, ("tail over 128 MiB", size, last)
    assert (k - 1) * c + last == size, ("coverage gap", size, c, k)
    if k == 1:
        assert c == size and size % 8 == 0, ("a lone chunk must equal the file", size, c, k)
    if size > 64 * 1024 * 1024:
        assert k >= 2, ("a file over the 64 MB cap can never be one chunk", size, c, k)
    if size % 8 != 0:
        assert k >= 2, ("unaligned size declared as 1 chunk — the EP.079/080 bug", size, c, k)
chk(all(tt_chunks(s) == ((s, 1) if s % 8 == 0 else (8, 1)) for s in (1, 8, 9, 15)),
    "the sub-16-byte band is answered best-effort (no legal plan exists) and never raises")
chk(True, "property sweep over 16 sizes: /8 chunks, floor count, oversized tail, full coverage, "
          "and the new law — a single chunk only when chunk_size == video_size")
cs, n = tt_chunks(4_000_000)
chk((cs, n) == (4_000_000, 1), "an aligned file still uploads as one exact chunk (never split for fun)")
cs, n = tt_chunks(5_000_001)
chk(cs % 8 == 0 and n == 2 and cs < 5_000_001, f"unaligned file splits instead of lying: {cs} × {n}")
chk(tt_chunks(5_000_003)[1] >= 2, "the size class that failed on EP.079/EP.080 now declares ≥2 chunks")
chk(all(tt_chunks(s)[1] >= 2 for s in (4_999_999, 5_000_001, 5_000_003, 8_000_001, 12_345_679)),
    "every unaligned size in our Shorts range splits, every aligned one stays whole")
chk(tt_chunks(0) == (0, 0) and tt_chunks(-5) == (0, 0), "empty/garbage size → (0,0), never a crash")

# the real upload path, against a fake transport
tmp = ROOT / "out"; tmp.mkdir(exist_ok=True)
f = tmp / "tt_probe.mp4"; f.write_bytes(b"\xa5" * 5_000_003)
calls = []
class Resp:
    def __init__(self, b=b"{}"): self._b = b
    def read(self): return self._b
def fake(req, timeout=None):
    if req.full_url.endswith("/init/"):
        calls.append(("init", json.loads(req.data)))
        return Resp(json.dumps({"data": {"upload_url": "https://tt/up/1", "publish_id": "p1"}}).encode())
    calls.append(("put", req.get_header("Content-range"), len(req.data), req.data[:2]))
    return Resp(b"ok")
os.environ["TIKTOK_ACCESS_TOKEN"] = "fake"
urllib.request.urlopen = fake
from src import multi_post as MP
res = MP.tiktok_video(f, "test caption")
put = [c for c in calls if c[0] == "put"]
init = [c for c in calls if c[0] == "init"][0][1]["source_info"]
chk(sum(p[2] for p in put) == 5_000_003, "every byte is sent, no truncation")
chk(len(put) >= 2 and put[-1][1].endswith("-5000002/5000003"),
    f"a 5,000,003-byte short now uploads as {len(put)} PUTs with the tail carrying the remainder",
    str([p[1] for p in put]))
chk(init["chunk_size"] % 8 == 0 and init["total_chunk_count"] == len(put),
    "declared chunk_size is 8-byte aligned and the count matches the PUTs we make")
chk("DRAFT" in res.get("tt", ""), "lane still reports the DRAFT law", str(res)[:80])
f.unlink(missing_ok=True)

# the doc example, uploaded for real through the fake transport
big = tmp / "tt_big.mp4"
big.write_bytes(b"Z" * 50_000_123)
calls.clear()
src_mod = sys.modules["src.multi_post"]
orig = src_mod.tt_chunks
src_mod.tt_chunks = lambda size, cap=64 * 1024 * 1024: orig(size, cap=10_000_000)
res2 = src_mod.tiktok_video(big, "big caption")
src_mod.tt_chunks = orig
puts2 = [c for c in calls if c[0] == "put"]
chk(len(puts2) == 5 and sum(p[2] for p in puts2) == 50_000_123,
    f"50,000,123 bytes → 5 PUTs covering every byte ({len(puts2)} puts)", str([p[2] for p in puts2]))
chk(puts2[-1][1] == "bytes 40000000-50000122/50000123",
    "the last chunk is the oversized tail, exactly as their docs show", puts2[-1][1])
chk("DRAFT" in res2.get("tt", ""), "big file still lands the DRAFT (no lane change)", str(res2)[:70])
big.unlink(missing_ok=True)
print("─" * 64); print(f"UT-41 · {'PASS' if not bad else 'FAIL'} — {ok} checks")
sys.exit(1 if bad else 0)
