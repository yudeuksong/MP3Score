# MP3Score · MP3 → 피아노 악보 (로컬 변환기)

MP3/WAV 음원을 **내 컴퓨터 안에서** 피아노 악보 초안(MusicXML·MIDI)으로 바꾸는 프로그램입니다.
음표 추론에는 Spotify의 오픈소스 모델 [Basic Pitch](https://github.com/spotify/basic-pitch)(Apache-2.0)를 사용합니다.
음원은 외부 서버로 보내지 않습니다.

> 자동 채보 결과는 **초안**입니다. MuseScore 등에서 열어 반드시 검토·수정하세요.

## 현재 공개 범위
- 이 저장소는 **소스 코드 배포**입니다. Python 3.11에서 직접 설치해 실행합니다.
- 설치가 필요 없는 Windows 포터블 실행 파일은 **아직 공개하지 않았습니다.** 동봉해야 하는 일부 구성요소(Microsoft VC++ 런타임, LGPL 오디오·수치 라이브러리)의 재배포 조건과 대응 소스 준비가 끝나지 않았기 때문입니다. 자세한 내용은 [docs/RELEASE-STATUS.md](docs/RELEASE-STATUS.md)를 보세요.

## 지원 범위
| 음원 | 지원 수준 | 설명 |
|---|---|---|
| 단선율 (피아노 한 손, 플루트, 허밍 등) | 좋음 | 음높이는 대체로 정확. 박자는 BPM 입력과 양자화 설정에 크게 좌우됨 |
| 피아노 다성음 (화음, 양손) | 보통 | 화음 음 일부 누락·추가 가능. 페달·잔향이 많으면 정확도 저하 |
| 보컬+반주 혼합곡 (찬양, 가요 등) | 실험적 | 음원 분리를 하지 않음. 보컬 선율을 정확히 뽑는다고 약속하지 않음 |

- 왼손/오른손 분리는 음역 기반 휴리스틱입니다(기본 C4 기준).
- 템포 자동 추정은 절반/두 배로 틀릴 수 있습니다. 곡의 BPM을 알면 직접 입력하세요.
- 합성 음원 시험 결과는 [docs/TEST_RESULTS.md](docs/TEST_RESULTS.md)에 있습니다. 실제 녹음의 정확도를 보장하지 않습니다.

## 설치 (Python 3.11 필요)
Basic Pitch 0.4.0은 Python 3.7~3.11만 지원합니다. 설치 스크립트는 프로젝트 폴더 안에 `.venv` 가상환경만 만들고 전역 설정은 바꾸지 않습니다.

### Windows
1. [python.org](https://www.python.org/downloads/)에서 Python 3.11.x를 설치합니다(py launcher 포함).
2. (권장) ffmpeg 설치: `winget install Gyan.FFmpeg`
3. `setup_windows.bat` 실행 → `run_windows.bat` 실행 → 브라우저에서 http://127.0.0.1:8765/

### Linux / macOS
```bash
./setup.sh   # python3.11 이 PATH에 있어야 함 (PYTHON=경로 로 지정 가능)
./run.sh     # http://127.0.0.1:8765/
```

### 수동 설치
```bash
python3.11 -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install --no-deps basic-pitch==0.4.0           # TensorFlow 강제 설치를 피하고 ONNX 모델 사용
```
`requirements-lock.txt`에 검증에 사용한 전체 의존성 버전이 있습니다. 의존성은 설치 시 PyPI에서 사용자가 직접 받습니다.

## 사용법
1. MP3/WAV를 끌어 놓고 음원 종류(피아노/단선율/혼합곡)를 고릅니다.
2. 필요하면 BPM·박자·양자화·음역·분할음·감도·분석 구간을 조절합니다.
3. **악보로 변환** → 미리보기 확인 → MusicXML·MIDI 저장.
4. PDF는 **브라우저로 인쇄 → PDF로 저장**을 쓰거나, MuseScore 4를 설치하면 자동 생성 경로를 쓸 수 있습니다(MuseScore 자동 PDF는 미검증).

명령줄: `python -m app.cli song.mp3 -o out --bpm 96 --mode piano`

## 제한과 안전장치
- 최대 50MB, 분석 구간 최대 10분. 긴 곡은 구간을 나누세요.
- 서버는 127.0.0.1에만 열리며, 다른 웹사이트에서 보낸 요청은 거부합니다.
- 업로드 원본은 변환 직후 삭제, 결과는 1시간 뒤 또는 종료 시 삭제합니다.

## 테스트
```bash
python -m pytest -q
```
테스트 음원은 코드가 직접 합성합니다(`tests/synth.py`). `samples/`의 MP3도 이 합성기로 만든 시험 음원입니다.

## 포터블 빌드 관련 파일
`PortableLauncher.cs`, `portable_launcher.py`, `portable_recovery.py`, `support/`, `tools/portable-smoke.ps1`은 향후 Windows 포터블 빌드용 실행기·검증 코드입니다. 이 저장소에는 실행 파일과 런타임이 포함되어 있지 않습니다.

## 라이선스
이 프로젝트 코드: [MIT](LICENSE) © MP3Score contributors.
제3자 구성요소는 각자의 라이선스를 따릅니다: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
Basic Pitch 모델과 코드는 이 저장소에 포함되지 않으며, 설치 시 PyPI에서 받습니다.
