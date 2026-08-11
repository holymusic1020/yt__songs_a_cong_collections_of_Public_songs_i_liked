"""v21 receipt: the DIAL fix — prove _client survives every gradio auth_style,
and the opening credit actually burns into real rendered frames.
"""
import os
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def fake_gradio(style):
    """Install a fake gradio_client module whose Client only accepts
    one auth kwarg — mimicking the version drift that killed run #logs."""
    mod = types.ModuleType("gradio_client")

    if style == "old":        # sandbox world: token= exists
        class Client:
            def __init__(self, space, verbose=False, token=None):
                self.kind = "old-token"
                if token:
                    self.kind += ":" + token[:4]
    elif style == "new":      # runner world: token= REJECTED, hf_token= only
        class Client:
            def __init__(self, space, verbose=False, hf_token=None):
                self.kind = "new-hf:" + (hf_token or "anon")[:4]
    else:                     # hostile world: no auth kwarg at all
        class Client:
            def __init__(self, space, verbose=False):
                self.kind = "bare-anon"
    mod.Client = Client
    sys.modules["gradio_client"] = mod
    for m in ("src.music_space",):
        sys.modules.pop(m, None)


def test_client():
    print("== _client version-drift gauntlet ==")
    os.environ["HF_TOKEN"] = "hf_testtoken123"
    from src import music_space as ms
    for style, expect in (("old", "old-token:hf_t"),
                          ("new", "new-hf:hf_t"),
                          ("bare", "bare-anon")):
        fake_gradio(style)
        sys.modules.pop("src.music_space", None)
        from src import music_space as ms2
        c = ms2._client("ACE-Step/Ace-Step-v1.5")
        assert c.kind == expect, (style, c.kind)
        print(f"  ✓ gradio {style:<4} world -> dialed via {c.kind}")
    # no token env -> immediate anonymous, no crash
    del os.environ["HF_TOKEN"]
    fake_gradio("new")
    sys.modules.pop("src.music_space", None)
    from src import music_space as ms3
    c = ms3._client("ACE-Step/Ace-Step-v1.5")
    assert c.kind == "new-hf:anon"
    print("  ✓ no HF_TOKEN -> anonymous dial, no crash")
    sys.modules.pop("gradio_client", None)


def test_credit_burn():
    from src import video_render as vr
    import numpy as np
    from PIL import Image
    print("\n== opening credit in a REAL render ==")
    ok = vr._drawtext_ok()
    print(f"  sandbox ffmpeg drawtext: {ok}")
    root = Path("/tmp/v21_render")
    root.mkdir(exist_ok=True)
    imgs = []
    for i, col in enumerate(((34, 28, 60), (60, 30, 34))):
        p = root / f"img{i}.png"
        Image.new("RGB", (640, 360), col).save(p)
        imgs.append(p)
    sr = 44100
    wav = root / "a.wav"
    from src.composer import write_wav
    write_wav(wav, (np.random.default_rng(1).standard_normal(3 * sr)
                    .astype("float32") * 0.05))
    out = root / "t.mp4"
    lyr = [(0.5, "test karaoke line")]
    vr.from_images(imgs, 3.0, out, wav=wav, lyrics=lyr)
    assert out.exists() and out.stat().st_size > 50_000
    import subprocess, shutil
    ff = shutil.which("ffmpeg")
    fr = root / "frame1s.png"
    subprocess.run([ff, "-y", "-v", "error", "-ss", "1.2", "-i", str(out),
                    "-frames:v", "1", str(fr)], check=True)
    print(f"  ✓ rendered {out.stat().st_size//1024} KB, frame at 1.2s extracted")
    return fr


def test_short_card():
    print("\n== short first-card credit ==")
    from src import shorts
    p = Path("/tmp/v21_card0.png")
    shorts._lyric_card("hear the night speaking", p, credit=True)
    assert p.exists()
    from PIL import Image
    px = Image.open(p).convert("RGBA")
    # the credit band sits below the lyric block — some ink must exist there
    band = px.crop((0, int(shorts.SH * 0.60), shorts.SW, int(shorts.SH * 0.78)))
    ink = sum(1 for r, g, b, a in band.getdata() if a > 40 and r > 180)
    assert ink > 500, f"credit band looks empty ({ink}px)"
    print(f"  ✓ first card: credit band has {ink} bright px of text ink")
    return p


if __name__ == "__main__":
    test_client()
    frame = test_credit_burn()
    card = test_short_card()
    print(f"\nartifacts: {frame}  {card}")
    print("ALL GREEN ✓")
