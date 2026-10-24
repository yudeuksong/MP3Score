# 제3자 구성요소

## 이 저장소에 직접 포함된 것
| 구성요소 | 버전 | 라이선스 | 위치 |
|---|---|---|---|
| OpenSheetMusicDisplay (공식 npm 빌드, 무수정) | 2.2.1 | BSD-3-Clause, © 2019 PhonicScore | `app/static/vendor/` (`OSMD-LICENSE.txt`, `OSMD-BUNDLED-DEPENDENCIES.txt`) |
| OSMD 번들 내부: VexFlow, JSZip(MIT 선택), pako, loglevel, typescript-collections | 번들 기준 | MIT 등 | `app/static/vendor/OSMD-BUNDLED-DEPENDENCIES.txt` |
| Starlette (포터블 실행본 복구용 원본 파일 묶음, 무수정) | 1.9.0 | BSD-3-Clause | `support/starlette-recovery.zip` 안의 `starlette-1.9.0.dist-info/licenses/LICENSE.md` |

## 설치 시 사용자가 PyPI에서 받는 것 (저장소에 미포함)
Spotify Basic Pitch 0.4.0과 ONNX 모델(Apache-2.0), ONNX Runtime(MIT), music21(BSD-3-Clause), librosa·resampy(ISC), NumPy·SciPy·scikit-learn(BSD 계열, 일부 바이너리 휠은 추가 구성요소 포함), FastAPI(MIT), uvicorn(BSD-3-Clause), soundfile(BSD-3-Clause, 동봉 libsndfile는 LGPL-2.1), soxr(LGPL-2.1-or-later) 등. 정확한 버전은 `requirements-lock.txt`, 휠 출처와 SHA-256은 `licenses/PYPI-WHEEL-PROVENANCE.json`에 있습니다. 각 패키지의 라이선스는 설치된 `*.dist-info`에서 확인할 수 있습니다.

## 선택 사항 (미포함)
- MuseScore 4 (GPL-3.0): 사용자가 별도 설치한 경우 외부 프로세스로만 호출합니다.
- ffmpeg: 사용자가 별도 설치합니다.
- MuScriptor(코드 MIT, 모델 CC BY-NC 4.0)는 사용하지 않으며 비교 조사 문서에만 언급합니다.

이 문서는 법률 자문이나 라이선스 원문을 대체하지 않습니다.
