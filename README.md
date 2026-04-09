# MP

- AI-friendly Windows install bundle: `ai_install/README.md`
- Portable single-env layout guide: [PORTABLE.md](/mnt/c/Users/dosky/anaconda3/envs/sgt/Multi-Play/PORTABLE.md)
- `씬분석` 스택은 이제 옵션 설치다. 기본 플레이어만 쓰면 `ai_install/install_windows.ps1` 기본 실행으로 충분하고, 필요한 경우에만 `-InstallSceneAnalysis`를 붙인다.
- Open-source notice set:
  - [LICENSE](/mnt/c/Users/dosky/anaconda3/envs/sgt/Multi-Play/LICENSE)
  - [THIRD_PARTY_NOTICES.md](/mnt/c/Users/dosky/anaconda3/envs/sgt/Multi-Play/THIRD_PARTY_NOTICES.md)

## Quick Install

Windows PowerShell에서 바로 실행할 명령:

기본 플레이어만:

```powershell
powershell -ExecutionPolicy Bypass -File .\ai_install\install_windows.ps1
```

플레이어 + 씬분석:

```powershell
powershell -ExecutionPolicy Bypass -File .\ai_install\install_windows.ps1 -InstallSceneAnalysis
```

이미 메인 env를 만든 상태에서 씬분석 core 패키지만 직접 추가:

```powershell
pip install numpy opencv-python scenedetect pillow
```

시스템 FFmpeg/VLC는 직접 관리하고 Python 패키지만 설치:

```powershell
powershell -ExecutionPolicy Bypass -File .\ai_install\install_windows.ps1 -InstallSceneAnalysis -SkipSystemDeps
```

## Dependencies

- 플레이어:
  `PyQt6`, `python-vlc`, `yt-dlp`
  시스템 런타임으로 `VLC desktop`, `FFmpeg`가 필요하다.
- 씬분석:
  core: `numpy`, `opencv-python`, `scenedetect`, `pillow`
  AI common: `torch`, `transformers`, `huggingface_hub`, `safetensors`, `accelerate`, `sentencepiece`
  decode/runtime: `TorchCodec` 우선, 실패 시 `OpenCV` 폴백
- 자막 생성/번역:
  기본 설치 번들에 포함되지 않는 optional helper 스택이다.
  - 자막 생성(ASR): 별도 helper env 권장. `faster-whisper`, `ctranslate2`, `av`
  - 자막 번역: `llama.cpp` (`llama-server.exe` 권장) + `TranslateGemma` GGUF
  - Windows GPU 경로는 메인 앱 env와 분리하는 쪽이 안전하다. 현재 프로젝트 기준 권장 helper env는 CUDA 12.x 계열이다.
  - 앱은 첫 실행 후 `MULTIPLAY_SUBTITLE_PYTHON`, `MULTIPLAY_LLAMA_BIN`, `MULTIPLAY_TRANSLATE_GGUF` 또는 dialog에서 고른 경로를 config에 기억한다.

## Licensing

- 이 저장소는 오픈소스 `GPL-3.0-or-later` 기준으로 배포한다.
- 자세한 프로젝트 라이선스는 [LICENSE](/mnt/c/Users/dosky/anaconda3/envs/sgt/Multi-Play/LICENSE)를 본다.
- 제3자 의존성과 배포 시 주의점은 [THIRD_PARTY_NOTICES.md](/mnt/c/Users/dosky/anaconda3/envs/sgt/Multi-Play/THIRD_PARTY_NOTICES.md)에 정리돼 있다.
- 설치판 기본 흐름은 `VLC`, `FFmpeg`, 모델 파일을 시스템/운영자 관리 대상으로 두므로, 이 저장소 자체는 그 바이너리들을 기본 번들로 재배포하지 않는다.

## Manual Install

Windows에서 수동으로 설치할 때는 아래 순서가 가장 단순하다. 기본 권장 경로는 `Conda + pip`지만, 일반 Python `venv`로도 같은 구성을 만들 수 있다.

### 설치 조합 한눈에 보기

| 구성 | 포함 패키지/런타임 | 빠지는 것 |
| --- | --- | --- |
| 기본 플레이어 | `PyQt6`, `python-vlc`, `yt-dlp`, `VLC`, `FFmpeg` | `numpy`, `opencv-python`, `scenedetect`, `pillow`, `torch`, `transformers`, 자막 AI helper |
| 플레이어 + 씬변화 | 기본 플레이어 + `numpy`, `opencv-python`, `scenedetect`, `pillow` | `torch`, `transformers`, 자막 AI helper |
| 플레이어 + 유사씬 AI | 플레이어 + 씬변화 + `torch`, `transformers`, `huggingface_hub`, `safetensors`, `accelerate`, `sentencepiece` | 자막 AI helper |
| 자막 생성 helper | 별도 helper env + `torch`, `faster-whisper`, `av` | 메인 앱/씬분석 패키지와는 분리 권장 |
| 자막 번역 helper | `llama.cpp`, GGUF | Python AI stack에 묶지 않음 |

### 0. 런타임 선택

- `Conda`가 이미 익숙하면:
  - 메인 앱 env 예시 이름: `multi-play`
  - 자막 생성 helper env 예시 이름: `multi-play-asr`
- 일반 Python만 쓸 경우:
  - 메인 앱 venv 예시 폴더: `.venv-multi-play`
  - 자막 생성 helper venv 예시 폴더: `.venv-multi-play-asr`

### 1. 플레이어만

이 단계에는 `numpy`, `opencv-python`, `scenedetect`, `pillow`가 들어가지 않는다. 씬변화/유사씬 기능이 필요할 때만 다음 단계를 추가한다.

Conda:

```powershell
conda create -n multi-play python=3.11 -y
conda activate multi-play
python -m pip install --upgrade pip
pip install PyQt6 python-vlc yt-dlp
```

일반 Python `venv`:

```powershell
py -3.11 -m venv .venv-multi-play
.\.venv-multi-play\Scripts\activate
python -m pip install --upgrade pip
pip install PyQt6 python-vlc yt-dlp
```

추가 시스템 설치:
- `VLC desktop`
- `FFmpeg`

### 2. 플레이어 + 씬변화 분석

여기서부터 `numpy`, `opencv-python`, `scenedetect`, `pillow`가 추가된다.

Conda:

```powershell
conda activate multi-play
pip install numpy opencv-python scenedetect pillow
```

일반 Python `venv`:

```powershell
.\.venv-multi-play\Scripts\activate
pip install numpy opencv-python scenedetect pillow
```

### 3. 플레이어 + 유사씬 AI

NVIDIA GPU면 현재 프로젝트 기준 `cu128` 라인을 권장한다. RTX 20/30/40/50 계열은 이 기준으로 맞추는 편이 이식성이 좋다.

Conda:

```powershell
conda activate multi-play
pip install torch --index-url https://download.pytorch.org/whl/cu128
pip install transformers huggingface_hub safetensors accelerate sentencepiece
```

일반 Python `venv`:

```powershell
.\.venv-multi-play\Scripts\activate
pip install torch --index-url https://download.pytorch.org/whl/cu128
pip install transformers huggingface_hub safetensors accelerate sentencepiece
```

선택 설치:

Conda:

```powershell
conda activate multi-play
pip install torchcodec
```

일반 Python `venv`:

```powershell
.\.venv-multi-play\Scripts\activate
pip install torchcodec
```

`torchcodec`는 유사씬/씬변화의 GPU decode 품질과 속도에 유리하지만, 설치가 안 되어도 앱은 `FFmpeg/OpenCV` 폴백으로 동작한다.

### 4. 자막 생성 helper

자막 생성은 메인 앱 env와 분리하는 것을 권장한다.

Conda:

```powershell
conda create -n multi-play-asr python=3.11 -y
conda activate multi-play-asr
python -m pip install --upgrade pip
pip install torch==2.10.0 --index-url https://download.pytorch.org/whl/cu128
pip install faster-whisper av
```

일반 Python `venv`:

```powershell
py -3.11 -m venv .venv-multi-play-asr
.\.venv-multi-play-asr\Scripts\activate
python -m pip install --upgrade pip
pip install torch==2.10.0 --index-url https://download.pytorch.org/whl/cu128
pip install faster-whisper av
```

기본 빠른 모델:
- `mobiuslabsgmbh/faster-whisper-large-v3-turbo`

품질 우선 모델:
- `Systran/faster-whisper-large-v3`

### 5. 자막 번역 helper

자막 번역은 Python 패키지보다 `llama.cpp` 바이너리와 GGUF 모델 파일이 핵심이다.

권장:
- `llama.cpp` Windows CUDA 12 build
- GGUF 모델 1개

예시 실행:

```powershell
llama-server.exe -m C:\path\model.gguf -ngl 99 -c 12800
```

앱에서 기억하는 환경변수:

```powershell
setx MULTIPLAY_SUBTITLE_PYTHON "C:\path\to\multi-play-asr\python.exe"
setx MULTIPLAY_LLAMA_BIN "C:\path\to\llama-server.exe"
setx MULTIPLAY_TRANSLATE_GGUF "C:\path\to\model.gguf"
```

예:
- Conda helper env: `C:\Users\<you>\anaconda3\envs\multi-play-asr\python.exe`
- Python venv helper: `C:\path\to\project\.venv-multi-play-asr\Scripts\python.exe`

### 6. 최소 설치 조합

- 플레이어만:
  `multi-play` env에 `PyQt6`, `python-vlc`, `yt-dlp`
- 플레이어 + 씬변화:
  위 구성 + `numpy`, `opencv-python`, `scenedetect`, `pillow`
- 플레이어 + 유사씬:
  위 구성 + `torch`, `transformers`, `huggingface_hub`, `safetensors`, `accelerate`, `sentencepiece`
- 자막 생성:
  별도 `multi-play-asr` env + `faster-whisper`
- 자막 번역:
  `llama.cpp` + GGUF

## Subtitle Add-ons

- 현재 앱은 자막 생성과 자막 번역을 `메인 앱 env` 밖의 helper runtime으로 붙이는 구조다.
- 권장 구성:
  - 메인 앱/씬분석: `multi-play` env 또는 `.venv-multi-play`
  - 자막 생성 helper: 별도 `multi-play-asr` env 또는 `.venv-multi-play-asr`
  - 자막 번역 helper: `llama.cpp` binary + GGUF model
- 이유:
  - `faster-whisper`와 `llama.cpp`는 Windows에서 CUDA/cuBLAS/cuDNN 조합 영향이 크다.
  - 메인 플레이어/씬분석 env를 안정적으로 두고, subtitle stack만 별도 관리하는 편이 배포 이식성이 좋다.
- 자세한 Windows 설치 순서는 [ai_install/README.md](/mnt/c/Users/dosky/anaconda3/envs/sgt/Multi-Play/ai_install/README.md)의 `Optional subtitle stack`과 `GPU generation guide`를 따른다.

## Lint

- 구조 lint 기본 규칙은 `신규 파일 실코드 200줄 이하`, `신규/증가 함수 실코드 30줄 이하`다.
- 레거시 대형 파일은 한 번에 전부 막지 않고, `HEAD` 대비 더 커진 경우만 구조 lint 에서 실패시킨다.
- 기본 실행은 `python3 tools/lint.py <변경한 .py 파일>` 이고, 인자를 생략하면 현재 변경된 Python 파일을 대상으로 돈다.
- 추가로 `ruff`를 같이 쓰려면 `python3 -m pip install -r requirements-lint.txt` 로 설치한다.
## Portable

포터블은 단순 파일 복사만으로 끝나지 않는다. 앱 트리 복사, `.venv` 생성, 런타임 폴더(`ffmpeg`, `vlc`, `llama`, `models`) 배치가 필요하다.

```powershell
powershell -ExecutionPolicy Bypass -File .\ai_install\assemble_portable.ps1 `
  -TargetDir C:\work\Multi-Play-Portable
```

```powershell
powershell -ExecutionPolicy Bypass -File .\ai_install\setup_portable_env.ps1 `
  -PortableRoot C:\work\Multi-Play-Portable
```

상세 구조와 옵션은 [PORTABLE.md](/mnt/c/Users/dosky/anaconda3/envs/sgt/Multi-Play/PORTABLE.md)를 본다.
