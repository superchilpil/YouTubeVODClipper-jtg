from pathlib import Path
import shutil
import imageio_ffmpeg

target_dir = Path("tools") / "ffmpeg"
target_dir.mkdir(parents=True, exist_ok=True)

source = Path(imageio_ffmpeg.get_ffmpeg_exe())
if not source.is_file():
    raise RuntimeError(f"Could not obtain FFmpeg: {source}")

target = target_dir / "ffmpeg.exe"
shutil.copy2(source, target)
print(f"Bundled FFmpeg: {target.resolve()}")

ffprobe = source.with_name("ffprobe.exe")
if ffprobe.is_file():
    shutil.copy2(ffprobe, target_dir / "ffprobe.exe")
    print("Bundled FFprobe.")
