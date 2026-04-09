# AI Install Bundle

This folder is meant to be read and executed by an AI agent or a technical operator on a Windows PC.

Goal:
- inspect the local machine
- decide whether CPU-only or GPU-assisted setup is possible
- install the missing Python dependencies
- verify that FFmpeg, VLC, the GUI runtime, and the AI stack are usable for this project

License note:
- The repository itself is documented by [LICENSE](/mnt/c/Users/dosky/anaconda3/envs/sgt/Multi-Play/LICENSE) and [THIRD_PARTY_NOTICES.md](/mnt/c/Users/dosky/anaconda3/envs/sgt/Multi-Play/THIRD_PARTY_NOTICES.md).
- This installed-edition flow prefers operator-managed `VLC`, `FFmpeg`, and model downloads instead of shipping those binaries inside the repository.

Files:
- `bootstrap_check.ps1`: scans the current PC and writes a machine report JSON
- `install_manifest.json`: structured install policy for AI agents
- `install_windows.ps1`: installs or updates a Windows environment using the report + manifest
- `post_install_check.py`: validates imports, FFmpeg, VLC, CUDA, `import main`, and a minimal GUI/VLC startup smoke test

Recommended flow:
1. Run `powershell -ExecutionPolicy Bypass -File .\ai_install\bootstrap_check.ps1`
2. Read `.\ai_install\output\system_report.json`
3. Run `powershell -ExecutionPolicy Bypass -File .\ai_install\install_windows.ps1`
4. Run `python .\ai_install\post_install_check.py --json-out .\ai_install\output\post_install_report.json`

Copy-paste install commands:

Base player only:

```powershell
powershell -ExecutionPolicy Bypass -File .\ai_install\install_windows.ps1
```

Base player + scene analysis:

```powershell
powershell -ExecutionPolicy Bypass -File .\ai_install\install_windows.ps1 -InstallSceneAnalysis
```

If the base env already exists and you only want the scene-analysis core packages manually:

```powershell
pip install numpy opencv-python scenedetect pillow
```

Base player + scene analysis without FFmpeg/VLC auto-install:

```powershell
powershell -ExecutionPolicy Bypass -File .\ai_install\install_windows.ps1 -InstallSceneAnalysis -SkipSystemDeps
```

Current install policy:
- prefer one shared FFmpeg path for decode + encode
- prefer standalone FFmpeg such as `C:\ffmpeg\bin\ffmpeg.exe`
- require VLC desktop installation for `python-vlc`
- include `yt-dlp` so page URLs like YouTube can be resolved into playable stream URLs
- use Conda when available, but plain Python `venv` is also supported
- default install flow now tries to provision missing FFmpeg/VLC automatically when `winget` is available
- allow CPU-only install when NVIDIA GPU / CUDA is not available
- install the `scene analysis` stack only when the operator explicitly passes `-InstallSceneAnalysis`
- subtitle generation / subtitle translation helper stack is not provisioned by `install_windows.ps1` yet; operators should install it separately

Recommended install split:
- base player only: `powershell -ExecutionPolicy Bypass -File .\ai_install\install_windows.ps1`
- base player + scene analysis: `powershell -ExecutionPolicy Bypass -File .\ai_install\install_windows.ps1 -InstallSceneAnalysis`
- skip FFmpeg/VLC auto-install only when you intentionally manage them yourself: `powershell -ExecutionPolicy Bypass -File .\ai_install\install_windows.ps1 -SkipSystemDeps`
- optional subtitle add-ons: keep them outside the main app env and manage them separately

Install split quick reference:
- base player only:
  - installs `PyQt6`, `python-vlc`, `yt-dlp`
  - does **not** install `numpy`, `opencv-python`, `scenedetect`, `pillow`, `torch`, `transformers`
- base player + scene analysis:
  - adds `numpy`, `opencv-python`, `scenedetect`, `pillow`
  - adds `torch`, `transformers`, `huggingface_hub`, `safetensors`, `accelerate`, `sentencepiece`
- subtitle helpers:
  - still separate from the main app env
  - ASR helper and `llama.cpp` are managed manually

Dependency split:
- Player:
  Python: `PyQt6`, `python-vlc`, `yt-dlp`
  System: `VLC`, `FFmpeg`
- Scene analysis:
  Core Python: `numpy`, `opencv-python`, `scenedetect`, `pillow`
  AI Python: `torch`, `transformers`, `huggingface_hub`, `safetensors`, `accelerate`, `sentencepiece`
  Decode/runtime: `TorchCodec` 우선, 실패 시 `OpenCV` 폴백
- Subtitle generation:
  Helper env Python: `faster-whisper`, `ctranslate2`, `av`
  Recommended Windows GPU helper runtime: `torch` CUDA 12.x wheel in the helper env so `cuBLAS/cuDNN` DLLs are available
  Default ASR model used by the app: `mobiuslabsgmbh/faster-whisper-large-v3-turbo`
- Subtitle translation:
  External runtime: `llama.cpp` (`llama-server.exe` preferred)
  Model: `TranslateGemma` GGUF, manually downloaded
  Current app behavior: remembers selected `llama` binary, GGUF path, source language, target language after first successful selection

Optional subtitle stack:
1. Create a separate helper env for ASR instead of adding `faster-whisper` into the main app env.
2. Recommended Windows helper env examples:

```powershell
conda create -n multi-play-asr python=3.11 -y
conda activate multi-play-asr
python -m pip install --upgrade pip
pip install torch==2.10.0 --index-url https://download.pytorch.org/whl/cu128
pip install faster-whisper av
```

```powershell
py -3.11 -m venv .venv-multi-play-asr
.\.venv-multi-play-asr\Scripts\activate
python -m pip install --upgrade pip
pip install torch==2.10.0 --index-url https://download.pytorch.org/whl/cu128
pip install faster-whisper av
```

3. CPU-only fallback examples:

```powershell
conda create -n multi-play-asr python=3.11 -y
conda activate multi-play-asr
python -m pip install --upgrade pip
pip install faster-whisper av
```

```powershell
py -3.11 -m venv .venv-multi-play-asr
.\.venv-multi-play-asr\Scripts\activate
python -m pip install --upgrade pip
pip install faster-whisper av
```

4. Install `llama.cpp` separately.
   Recommended binary on Windows:
   - NVIDIA GPU: `Windows x64 (CUDA 12)` build
   - CPU-only: `Windows x64 (CPU)` build
5. Download a `TranslateGemma` GGUF manually. The app does not auto-download translation models.
6. First run behavior:
   - `자막 생성` will auto-detect a Python that can import `faster_whisper`, then remember it as `subtitle_asr_python`
   - `자막 번역` will auto-detect or ask for `llama-server.exe` and a GGUF model, then remember them in config
7. Useful overrides:
   - `MULTIPLAY_SUBTITLE_PYTHON`
   - `MULTIPLAY_LLAMA_BIN`
   - `MULTIPLAY_TRANSLATE_GGUF`

GPU generation guide:
- GTX 10 / GTX 16:
  - Treat CPU path as the safe baseline.
  - If you want GPU subtitle generation, verify the helper env on that PC first; keep `faster-whisper` isolated from the main app env.
  - For translation, prefer smaller GGUF such as `TranslateGemma 4B Q4_K_M`.
- RTX 20:
  - Recommended split: main app in `multi-play` env or `.venv-multi-play`, subtitles in separate `multi-play-asr` env or `.venv-multi-play-asr`.
  - `faster-whisper turbo` GPU path is usually the first option to try.
  - For translation, `TranslateGemma 4B Q4_K_M` or `Q5_K_M` is the practical target.
- RTX 30:
  - Recommended full GPU helper path: separate subtitle helper env with CUDA 12.x `torch` wheel + `faster-whisper`, plus `llama.cpp` CUDA 12 build.
  - `TranslateGemma 4B Q5_K_M` is the default recommendation.
- RTX 40:
  - Same recommendation as RTX 30.
  - If VRAM is comfortable, translation can move from `Q4_K_M` to `Q5_K_M` or higher.
- RTX 50:
  - Do not tie subtitle helpers to the main app env. Keep a separate helper env.
  - Prefer CUDA 12.x helper tooling for portability across PCs.
  - Current project guidance is separate subtitle helper env + `torch` CUDA 12.8 wheel + `llama.cpp` Windows CUDA 12 build.
  - For translation, start with `TranslateGemma 4B Q5_K_M`.

Notes on the 10~50 guide:
- The GPU guide above is project-side deployment guidance, not a strict vendor support matrix.
- The main point is portability: keep the player/scene-analysis env stable, and keep subtitle ASR/translation runtimes isolated.
- `faster-whisper` currently expects CUDA 12 libraries and cuDNN 9 on GPU, and current `llama.cpp` releases provide both Windows CUDA 12 and CUDA 13 builds.

Launcher notes:
- install writes `run_multi_play_local.bat` in the project root using the resolved `conda` or `python` executable path
- checked-in `run_multi_play.bat` now delegates to `run_multi_play_local.bat` first when that launcher exists

Notes for AI agents:
- read `install_manifest.json` before running the installer
- do not assume CUDA is available just because NVIDIA hardware exists
- after install, treat `post_install_check.py` as the source of truth for success/failure
## Portable

포터블 조립은 2단계다.

1. 앱 트리와 런타임 폴더 구조 만들기
2. 포터블 `.venv` 만들고 requirements 설치하기

```powershell
powershell -ExecutionPolicy Bypass -File .\ai_install\assemble_portable.ps1 `
  -TargetDir C:\work\Multi-Play-Portable
```

```powershell
powershell -ExecutionPolicy Bypass -File .\ai_install\setup_portable_env.ps1 `
  -PortableRoot C:\work\Multi-Play-Portable
```

추가 런타임을 같이 복사하고 싶으면 `-FfmpegSource`, `-VlcSource`, `-LlamaSource`, `-GgufModels`, `-WhisperModelDirs`를 넘긴다.
