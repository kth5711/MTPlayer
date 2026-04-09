# Notice Packaging Checklist

이 문서는 `Multi-Play`를 오픈소스로 배포할 때, 배포물에 같이 넣어야 할
고지 파일과 확인 항목을 짧게 정리한 운영용 체크리스트다.

## Source Release

소스 배포에는 아래 파일을 포함한다.

- [LICENSE](/mnt/c/Users/dosky/anaconda3/envs/sgt/Multi-Play/LICENSE)
- [THIRD_PARTY_NOTICES.md](/mnt/c/Users/dosky/anaconda3/envs/sgt/Multi-Play/THIRD_PARTY_NOTICES.md)
- [README.md](/mnt/c/Users/dosky/anaconda3/envs/sgt/Multi-Play/README.md)
- [ai_install/README.md](/mnt/c/Users/dosky/anaconda3/envs/sgt/Multi-Play/ai_install/README.md)

## Installed-Edition Release

설치판 배포 또는 릴리스 안내에는 아래 원칙을 유지한다.

- 저장소 기본 배포물에는 `VLC`, `FFmpeg`, Hugging Face 모델, GGUF 모델을
  기본 포함하지 않는다.
- 운영자 또는 사용자가 직접 설치/다운로드하도록 안내한다.
- 설치 가이드는 [README.md](/mnt/c/Users/dosky/anaconda3/envs/sgt/Multi-Play/README.md)
  와 [ai_install/README.md](/mnt/c/Users/dosky/anaconda3/envs/sgt/Multi-Play/ai_install/README.md)
  를 기준으로 유지한다.

## If You Bundle Third-Party Binaries

아래 항목을 실제 배포물에 넣는 경우에는 해당 upstream 라이선스 파일도 같이
동봉한다.

- `VLC`
- `FFmpeg`
- `llama.cpp`
- SigLIP / Whisper / GGUF 모델 파일

이 경우 [THIRD_PARTY_NOTICES.md](/mnt/c/Users/dosky/anaconda3/envs/sgt/Multi-Play/THIRD_PARTY_NOTICES.md)
만으로 끝내지 말고, **그 배포물에 실제로 들어간 artifact 기준**으로 LICENSE 또는
모델 카드 파일을 추가한다.

## Final Release Check

릴리스 직전 아래를 다시 확인한다.

1. 루트 [LICENSE](/mnt/c/Users/dosky/anaconda3/envs/sgt/Multi-Play/LICENSE)가 최신인지.
2. [THIRD_PARTY_NOTICES.md](/mnt/c/Users/dosky/anaconda3/envs/sgt/Multi-Play/THIRD_PARTY_NOTICES.md)의 의존성 목록이 현재 설치 가이드와 맞는지.
3. `PyQt6`, `python-vlc`, `opencv-python`, `transformers`, `torchcodec` 같은 핵심 의존성 메타데이터가 크게 바뀌지 않았는지.
4. 실제 배포물에 바이너리/모델을 포함했다면 그 upstream 라이선스 파일까지 동봉했는지.
