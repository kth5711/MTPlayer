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
1. Run `powershell -ExecutionPolicy Bypass -File .\install\bootstrap_check.ps1`
2. Read `.\install\output\system_report.json`
3. Run `powershell -ExecutionPolicy Bypass -File .\install\install_windows.ps1`
4. Run `python .\install\post_install_check.py --json-out .\install\output\post_install_report.json`

Copy-paste install commands:

Base player only:

```powershell
powershell -ExecutionPolicy Bypass -File .\install\install_windows.ps1
```

Base player + scene analysis:

```powershell
powershell -ExecutionPolicy Bypass -File .\install\install_windows.ps1 -InstallSceneAnalysis
```

If the base env already exists and you only want the scene-analysis core packages manually:

```powershell
pip install numpy opencv-python scenedetect pillow
```

Base player + scene analysis without FFmpeg/VLC auto-install:

```powershell
powershell -ExecutionPolicy Bypass -File .\install\install_windows.ps1 -InstallSceneAnalysis -SkipSystemDeps
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
- base player only: `powershell -ExecutionPolicy Bypass -File .\install\install_windows.ps1`
- base player + scene analysis: `powershell -ExecutionPolicy Bypass -File .\install\install_windows.ps1 -InstallSceneAnalysis`
- skip FFmpeg/VLC auto-install only when you intentionally manage them yourself: `powershell -ExecutionPolicy Bypass -File .\install\install_windows.ps1 -SkipSystemDeps`
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
1. If the main app env is already stable on `CUDA 12.x`, you can install ASR dependencies into that same env.
2. Same-env activation examples:

```powershell
conda activate multi-play
```

```powershell
.\.venv-multi-play\Scripts\activate
```

3. Then install the GPU ASR packages:

```powershell
python -m pip install --upgrade pip
pip install torch==2.10.0 --index-url https://download.pytorch.org/whl/cu128
pip install faster-whisper av
```

4. If you are on `CUDA 13`, or that PC has DLL/runtime conflicts, create a separate helper env for ASR instead.
5. Separate helper env creation/activation examples:

```powershell
conda create -n multi-play-asr python=3.11 -y
conda activate multi-play-asr
```

```powershell
py -3.11 -m venv .venv-multi-play-asr
.\.venv-multi-play-asr\Scripts\activate
```

6. Then run the same GPU ASR package install commands from step 3.

7. CPU-only fallback:

Conda or venv activation is the same as above. After activation, run:

```powershell
python -m pip install --upgrade pip
pip install faster-whisper av
```

8. Install `llama.cpp` separately.
   Recommended binary on Windows:
   - NVIDIA GPU: `Windows x64 (CUDA 12)` build
   - CPU-only: `Windows x64 (CPU)` build
9. Download a `TranslateGemma` GGUF manually. The app does not auto-download translation models.
10. First run behavior:
   - `자막 생성` will auto-detect a Python that can import `faster_whisper`, then remember it as `subtitle_asr_python`
   - `자막 번역` will auto-detect or ask for `llama-server.exe` and a GGUF model, then remember them in config
11. Useful overrides:
   - `MULTIPLAY_SUBTITLE_PYTHON`
   - `MULTIPLAY_LLAMA_BIN`
   - `MULTIPLAY_TRANSLATE_GGUF`

GPU generation guide:
- GTX 10 / GTX 16:
  - Treat CPU path as the safe baseline.
  - If you want GPU subtitle generation, verify imports and runtime on that PC first. Same env is possible, but a separate helper env is still the safer fallback.
  - For translation, prefer smaller GGUF such as `TranslateGemma 4B Q4_K_M`.
- RTX 20:
  - Same env is usually fine when `torch`/`faster-whisper`/`av` already work together.
  - If that PC shows DLL/runtime conflicts, split subtitles into `multi-play-asr` or `.venv-multi-play-asr`.
  - `faster-whisper turbo` GPU path is usually the first option to try.
  - For translation, `TranslateGemma 4B Q4_K_M` or `Q5_K_M` is the practical target.
- RTX 30:
  - `CUDA 12.x` same-env path is acceptable if the main env is already stable.
  - If you hit DLL/runtime conflicts, move subtitles into a separate helper env with CUDA 12.x `torch` wheel + `faster-whisper`.
  - `TranslateGemma 4B Q5_K_M` is the default recommendation.
- RTX 40:
  - Same recommendation as RTX 30.
  - If VRAM is comfortable, translation can move from `Q4_K_M` to `Q5_K_M` or higher.
- RTX 50:
  - Separate helper env is still the default recommendation.
  - Prefer CUDA 12.x helper tooling for portability across PCs.
  - Current project guidance is separate subtitle helper env + `torch` CUDA 12.8 wheel + `llama.cpp` Windows CUDA 12 build.
  - For translation, start with `TranslateGemma 4B Q5_K_M`.

Notes on the 10~50 guide:
- The GPU guide above is project-side deployment guidance, not a strict vendor support matrix.
- The main point is portability: `CUDA 13` 또는 불안정 조합이면 subtitle ASR/translation runtimes를 분리하고, `CUDA 12.x`에서 이미 안정적인 env라면 같은 env도 허용한다.
- `faster-whisper` currently expects CUDA 12 libraries and cuDNN 9 on GPU, and current `llama.cpp` releases provide both Windows CUDA 12 and CUDA 13 builds.

Launcher notes:
- install writes `run_multi_play_local.bat` in the project root using the resolved `conda` or `python` executable path
- checked-in `run_multi_play.bat` now delegates to `run_multi_play_local.bat` first when that launcher exists
- checked-in launchers target `app\main.py`, while keeping `run_multi_play.bat` and `run_multi_play.vbs` in the repo root as the Windows entrypoints

Notes for AI agents:
- read `install_manifest.json` before running the installer
- do not assume CUDA is available just because NVIDIA hardware exists
- after install, treat `post_install_check.py` as the source of truth for success/failure
