# YouTube VOD Clipper

A Windows desktop app for selecting and exporting a time range from a YouTube VOD. The preview uses YouTube's embedded player directly; it does not download a separate preview copy of the VOD.

The interface uses an original JTG-inspired dark desktop design with a compact sidebar, clear section cards, blue accent controls, and a dedicated preview/timeline workspace. It is not affiliated with SignalRGB.

## Features

- Embedded YouTube preview with an on-player start/end selection timeline.
- Editable start/end timestamps: `HH:MM:SS`, `MM:SS`, seconds, and compact numeric times such as `001929` for `00:19:29`.
- Fast or exact clipping mode.
- Best available, 1080p, 720p, or 480p output quality.
- Selectable output directory.
- FFmpeg bundled into the standalone Windows executable by the build process.
- Automated Windows x64 builds through GitHub Actions.

## Build locally on Windows

Requirements: Python 3.11+ and the Microsoft Edge WebView2 Runtime. An internet connection is required to install Python packages and obtain FFmpeg during the build.

1. Extract/clone this repository.
2. Run `install.bat` to build and launch the app, or run `build_exe.bat` to build without launching.
3. The executable is written to `dist/YouTubeVODClipper.exe`.

## Automated GitHub build

The `Build Windows App` workflow runs on pushes to `main`, pull requests, manual dispatch, and version tags (`v*`). Each run uploads a `YouTubeVODClipper-Windows-x64` artifact. Pushing a version tag such as `v4.0.0` also creates a GitHub Release containing the executable.

## Notes

- Some videos cannot play in an embedded player because of owner restrictions, age restrictions, or YouTube account/region requirements.
- The preview is provided by YouTube; actual clipping is performed by yt-dlp and FFmpeg.
- Keep third-party notices for dependencies when redistributing builds.
