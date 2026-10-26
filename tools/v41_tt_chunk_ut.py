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
chk(cs % 8 == 0 and n == 1 and cs < 5_000_003,
    f"odd size → legal chunk {cs}, count {n} (floor: the tail rides inside it)", f"{cs},{n}")
chk(tt_chunks(50_000_123, cap=10_000_000) == (10_000_000, 5),
    "TikTok's documented example reproduced exactly: 50,000,123 / 10,000,000 → 5 chunks")
for size in (1, 8, 9, 655_357, 1_000_003, 5_000_003, 64 * 1024 * 1024, 64 * 1024 * 1024 + 1,
             130_000_000, 137_423_105, 500_000_001, 1_073_741_824):
    c, k = tt_chunks(size)
    assert c % 8 == 0, ("chunk not /8", size, c)
    assert c <= max(size, 8), ("chunk bigger than file", size, c)
    assert k == max(1, size // c), ("count != floor(size/chunk)", size, c, k)
    last = size - (k - 1) * c
    assert 0 < last <= 2 * c, ("tail chunk out of contract", size, c, k, last)
    assert last <= 128 * 1024 * 1024, ("tail over 128 MiB", size, last)
    assert (k - 1) * c + last == size, ("coverage gap", size, c, k)
chk(True, "property sweep over 12 sizes: floor count, /8 chunks, oversized tail, full coverage")
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
chk(len(put) == 1 and put[0][1] == "bytes 0-5000002/5000003",
    "one PUT for a 5 MB short, range covering the WHOLE file", str([p[1] for p in put]))
chk(init["chunk_size"] % 8 == 0 and init["total_chunk_count"] == 1,
    "declared chunk_size is 8-byte aligned and count matches floor(size/chunk)")
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
