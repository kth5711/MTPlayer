# decord CUDA 12.x (Windows) 빌드 가이드

목표: `pip install decord`로 GPU 디코딩이 안 잡히는 환경에서, CUDA 12.x 대응 decord를 소스 빌드로 설치합니다.

## 1) 사전 준비

- NVIDIA 드라이버 + CUDA Toolkit 12.x 설치
- Visual Studio Build Tools 2022 (Desktop development with C++)
- CMake, Git
- Python 가상환경(프로젝트 실행 환경과 동일 권장)

확인:

```bat
nvcc --version
cmake --version
python -V
```

## 2) 빌드 의존성 설치

```bat
python -m pip install -U pip setuptools wheel
python -m pip install numpy cmake ninja
```

## 3) 소스 코드 받기

```bat
git clone --recursive https://github.com/dmlc/decord.git
cd decord
mkdir build
cd build
```

## 4) CUDA 빌드 (RTX 50xx: sm_120)

아래 예시는 Visual Studio 2022 기준입니다.

```bat
cmake .. -G "Visual Studio 17 2022" -A x64 -DUSE_CUDA=ON -DCMAKE_BUILD_TYPE=Release -DCMAKE_CUDA_ARCHITECTURES=120
cmake --build . --config Release
```

참고:

- `-DCMAKE_CUDA_ARCHITECTURES=120`은 RTX 50xx(sm_120) 타겟입니다.
- CMake가 CUDA를 못 찾으면 CUDA Toolkit 경로/환경변수를 먼저 점검하세요.

## 5) 파이썬 패키지 설치

```bat
cd ..\python
python setup.py bdist_wheel
python -m pip install --force-reinstall dist\decord-*.whl
```

## 6) 동작 확인

```bat
python -c "from decord import VideoReader, cuda; vr=VideoReader('sample.mp4', ctx=cuda(0)); print('ok', len(vr))"
```

실패 시 체크:

- 여전히 CPU로만 열리면, 다른 환경(베이스/타 venv)에 설치된 decord를 먼저 제거 후 재설치
- 프로젝트 실행 환경의 `python -c "import sys; print(sys.executable)"` 경로 확인
