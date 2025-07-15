# NiceDiffusion

Stable Diffusion 모델을 사용한 이미지 생성 및 편집 도구입니다.

## 시스템 요구사항

- Python 3.12 이상
- CUDA 지원 GPU (선택사항, CPU만으로도 실행 가능)
- 최소 8GB RAM (GPU 사용 시 16GB 권장)

## 설치 방법

### Windows

1. Python 3.12를 설치합니다: https://www.python.org/downloads/
2. 프로젝트 폴더에서 가상환경을 생성하고 활성화합니다:
```cmd
python -m venv venv
venv\Scripts\activate.bat
```

3. PyTorch를 CUDA 버전에 맞게 설치합니다:
```cmd
# CUDA 11.8 사용 시
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# CUDA 12.1 사용 시  
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# CPU만 사용 시
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
```

4. 나머지 의존성을 설치합니다:
```cmd
pip install -r requirements_win.txt
```

5. 프로그램을 실행합니다:
```cmd
python main.py
```

### Linux (Ubuntu 22.04)

1. Python 3.12를 설치합니다:
```bash
sudo apt update
sudo apt install python3.12 python3.12-venv python3.12-pip
```

2. 프로젝트 폴더에서 가상환경을 생성하고 활성화합니다:
```bash
python3.12 -m venv venv
source venv/bin/activate
```

3. PyTorch를 CUDA 버전에 맞게 설치합니다:
```bash
# CUDA 11.8 사용 시
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# CUDA 12.1 사용 시
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# CPU만 사용 시
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
```

4. 나머지 의존성을 설치합니다:
```bash
pip install -r requirements_linux.txt
```

5. 프로그램을 실행합니다:
```bash
python main.py
```

## 주요 기능

- **텍스트-이미지 생성**: 프롬프트를 입력하여 이미지 생성
- **이미지-이미지 변환**: 기존 이미지를 기반으로 새로운 이미지 생성
- **메타데이터 관리**: 생성된 이미지의 파라미터 정보 저장 및 로드
- **LoRA 모델 지원**: 커스텀 LoRA 모델 적용
- **포즈 편집**: ControlNet을 활용한 포즈 제어
- **실시간 미리보기**: 생성 과정의 실시간 확인
- **히스토리 관리**: 생성된 이미지 히스토리 저장 및 복원
- **자동 파라미터 적용**: 메타데이터에서 파라미터 자동 로드
- **토큰 제한 관리**: 프롬프트 자동 토큰화 및 길이 제한
- **다양한 샘플러 지원**: Euler, DPM++, DDIM 등 다양한 샘플러

## 프로젝트 구조

```
src/
├── nicediff/
│   ├── core/           # 핵심 기능 (상태 관리, 오류 처리)
│   ├── domains/        # 도메인 로직 (이미지 생성, 처리)
│   ├── pages/          # UI 페이지
│   ├── services/       # 서비스 레이어 (모델 스캔, 메타데이터 파싱)
│   ├── ui/             # UI 컴포넌트
│   └── utils/          # 유틸리티 함수
├── models/             # 모델 파일 저장소
├── outputs/            # 생성된 이미지 저장소
└── config.toml         # 설정 파일
```

## 설정

`config.toml` 파일에서 다음 설정을 변경할 수 있습니다:

- 모델 경로
- 기본 생성 파라미터
- UI 설정
- 성능 최적화 옵션

## 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

## 문제 해결

### CUDA 관련 문제
- NVIDIA 드라이버가 최신 버전인지 확인
- CUDA Toolkit이 올바르게 설치되었는지 확인
- GPU 메모리 부족 시 배치 크기 조정

### 메모리 부족 문제
- 배치 크기 감소
- 이미지 해상도 조정
- xformers 최적화 활성화

### 설치 문제
- Python 3.12 이상 사용 확인
- 가상환경 재생성 시도
- pip 캐시 정리: `pip cache purge`

### 런타임 오류
- **torchsde 누락**: `pip install torchsde>=0.2.6` 실행
- **Async 콜백 오류**: 프로그램 재시작으로 해결
- **토큰 제한 경고**: 프롬프트가 77 토큰을 초과하면 자동으로 잘림
- **메모리 부족**: 배치 크기 감소 또는 이미지 해상도 조정

### 성능 최적화
- xformers 설치로 메모리 효율성 향상
- PyTorch 2.0+ SDPA 최적화 자동 적용
- SD15/SDXL 모델별 최적화 설정 자동 적용 
