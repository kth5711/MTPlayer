# Third-Party Notices

This repository is distributed as an open-source Windows desktop application.
The installed-edition workflow expects several third-party runtimes and models
to be installed or downloaded separately by the operator.

This file is a practical notice summary for this repository. It is not legal
advice.

## Project License

- This repository is published under `GPL-3.0-or-later`.
- See [LICENSE](/mnt/c/Users/dosky/anaconda3/envs/sgt/Multi-Play/LICENSE).

## Distribution Model

- The checked-in installed edition does **not** bundle FFmpeg, VLC, subtitle
  models, or Hugging Face models by default.
- `install/install_windows.ps1` installs Python packages and can provision
  system dependencies on the target PC.
- If you later redistribute bundled FFmpeg/VLC binaries or model files, you
  must carry the relevant upstream licenses and notices with that bundle.

## Core Python Dependencies

- `PyQt6`
  - License: `GPL v3`
  - Source of truth in local metadata:
    `Lib/site-packages/PyQt6-6.7.1.dist-info/METADATA`
- `python-vlc`
  - License: `LGPL-2.1-or-later`
  - Source of truth in local metadata:
    `Lib/site-packages/python_vlc-3.0.21203.dist-info/METADATA`
- `yt-dlp`
  - Upstream project license should be checked from the installed package
    metadata or upstream repository at release time.

## Optional Scene Analysis Dependencies

- `numpy`
  - License family: BSD
- `opencv-python`
  - License: Apache-2.0
- `scenedetect`
  - License: BSD-3-Clause
- `pillow`
  - Upstream project license should be checked from installed metadata at
    release time.
- `torch`
  - PyTorch license files are shipped inside its installed package metadata.
- `transformers`
  - License: Apache-2.0
- `huggingface_hub`
  - License: Apache
- `safetensors`
  - Apache Software License classifier in installed metadata.
- `accelerate`
  - License: Apache
- `sentencepiece`
  - Upstream project license should be checked from installed metadata at
    release time.
- `torchcodec`
  - License: BSD 3-Clause

## Optional Subtitle Helper Dependencies

- `faster-whisper`
- `ctranslate2`
  - License: MIT
- `av`
  - Upstream project license should be checked from installed metadata at
    release time.

These subtitle helpers are intentionally kept outside the main app env in the
recommended install flow.

## System Dependencies

- `VLC desktop`
  - Recommended as a separately installed system dependency.
  - This repository uses `python-vlc` to talk to the local VLC runtime.
- `FFmpeg`
  - Recommended as a separately installed system dependency.
  - This repository expects a shared FFmpeg binary for decode/export paths.
  - If you redistribute a specific FFmpeg build, verify whether that build is
    `LGPL` or `GPL` and carry the appropriate upstream notices.

## Optional Models

The installed edition can use optional third-party models for scene analysis or
subtitle workflows. These are not bundled by default in the repository.

- `google/siglip2-base-patch16-224`
  - Used for similar-scene search when the optional AI stack is installed.
- `mobiuslabsgmbh/faster-whisper-large-v3-turbo`
  - Default fast subtitle generation model.
- `Systran/faster-whisper-large-v3`
  - Higher-quality subtitle generation model.
- Translation GGUF models
  - Operator-managed, manually downloaded, and configured separately.

Model redistribution and notice obligations depend on each upstream model card.
If you bundle models in a release, include each model's license or model card
with the bundle.

## Operator Checklist

- Keep this repository's [LICENSE](/mnt/c/Users/dosky/anaconda3/envs/sgt/Multi-Play/LICENSE)
  with source distributions.
- Keep this
  [THIRD_PARTY_NOTICES.md](/mnt/c/Users/dosky/anaconda3/envs/sgt/Multi-Play/THIRD_PARTY_NOTICES.md)
  with source or binary distributions.
- If you redistribute bundled VLC/FFmpeg/model files, add the upstream license
  texts for those exact artifacts.
- If you publish a packaged release, verify installed package metadata on the
  release machine before finalizing notices.
