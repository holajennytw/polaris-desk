"""Render promo.html to MP4: seek deterministic frames, capture, encode."""
import pathlib, subprocess, sys, time
from playwright.sync_api import sync_playwright
import imageio_ffmpeg

HERE = pathlib.Path(__file__).parent
FRAMES = HERE / "frames"
FRAMES.mkdir(exist_ok=True)
FPS, DUR = 24, 46.0
N = int(FPS * DUR)

t0 = time.time()
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
    pg.goto((HERE / "promo.html").absolute().as_uri())
    pg.evaluate("document.fonts.ready")
    for i in range(N):
        t = i / FPS
        pg.evaluate(f"SEEK({t})")
        pg.screenshot(path=str(FRAMES / f"f{i:05d}.jpg"), type="jpeg", quality=92)
        if i % 120 == 0:
            print(f"frame {i}/{N} ({time.time()-t0:.0f}s)", flush=True)
    b.close()
print(f"capture done in {time.time()-t0:.0f}s", flush=True)

ff = imageio_ffmpeg.get_ffmpeg_exe()
out = HERE / "polaris_工作紀實_v1.mp4"
cmd = [ff, "-y", "-framerate", str(FPS), "-i", str(FRAMES / "f%05d.jpg"),
       "-c:v", "libx264", "-preset", "slow", "-crf", "19",
       "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)]
subprocess.run(cmd, check=True, capture_output=True)
print("encoded:", out, out.stat().st_size, "bytes")
