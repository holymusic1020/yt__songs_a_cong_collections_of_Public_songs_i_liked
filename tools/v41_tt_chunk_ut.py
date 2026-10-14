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

from src.multi_post import tt_chunks

chk(tt_chunks(4_000_000) == (4_000_000, 1), "8-byte-aligned file → 1 chunk (old good case preserved)")
cs, n = tt_chunks(5_000_003)
chk(cs % 8 == 0 and n == 2 and cs < 5_000_003 <= cs * n,
    f"odd-size file → legal chunk ({cs}) + {n} chunks", f"{cs},{n}")
cs, n = tt_chunks(26_000_001)
chk(cs == 8_000_000 and n == 4, f"big file → 8 MB slices, {n} chunks")
for size in (1, 8, 9, 655_357, 1_000_003, 7_999_999, 8_000_001, 64_000_001, 137_423_105):
    c, k = tt_chunks(size)
    assert c % 8 == 0, (size, c)
    assert k == -(-size // c), (size, c, k)
    assert (k - 1) * c < size <= k * c, (size, c, k)
chk(True, "property sweep: chunk_size always a multiple of 8 and the count always covers the file")
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
chk(init["chunk_size"] % 8 == 0 and init["total_chunk_count"] == len(put) == 2,
    "init declares exactly what gets PUT", f"{init} vs {len(put)} puts")
chk(sum(p[2] for p in put) == 5_000_003, "every byte is sent, no truncation")
chk(put[0][1] == "bytes 0-4999999/5000003" and put[1][1] == "bytes 5000000-5000002/5000003",
    "Content-Range headers are the real ranges", str([p[1] for p in put]))
chk("DRAFT" in res.get("tt", ""), "lane still reports the DRAFT law", str(res)[:80])
f.unlink(missing_ok=True)
print("─" * 64); print(f"UT-41 · {'PASS' if not bad else 'FAIL'} — {ok} checks")
sys.exit(1 if bad else 0)
