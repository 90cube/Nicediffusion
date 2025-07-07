 Nicediffusion

![aidraw_simple_flat_logo_--ar_1716_--profile_5h5ugbf_--dref_ht_a5ab635c-b51a-4c00-a63c-383b2a766d5f_3](https://github.com/user-attachments/assets/3e8f7682-e14d-4566-a1d1-3d4f91b9eb0d)

# NiceDiffusion - Stable diffusion 기반의 이미지 생성 웹 어플리케이션

## ✨ 프로젝트 소개

**NiceDiffusion**은 AI 이미지 생성 도구인 A1111의 WebUI와 [ComfyUI](https://github.com/comfyanonymous/ComfyUI)를 계승할 목적 입니다.
쉬운 사용에 초점을 맞춰 제작 중이며, 이미지 편집과 더 나아가 컨텐츠 전체 장면의 시놉시스 제작에 도움을 줄 수 있는 툴을 개발 할 예정입니다.
현재는 Window 버전으로만 제작 중 입니다.

## 🚀 주요 기능

**다양한 Diffusion 모델 지원**: SDXL, SD1.5 등 여러 Stable Diffusion 모델과 커스텀 체크포인트 지원
**고도화된 프롬프트 관리**: T5 CLIP 기반 프롬프트 또는 WD Tagger 기반 태그를 활용한 정확한 이미지 제어
**ComfyUI 워크플로우 자동화**: 특정 조건에 따른 이미지 생성 파이프라인 자동 실행 (예: 특정 프롬프트 리스트 기반 배치 생성)
**파라미터 스위칭 및 실험**: 이미지 생성 파라미터(CFG, Step 등)를 쉽게 변경하고 비교하는 기능
**시각적 워크플로우 편집**: ComfyUI의 강력한 노드 기반 인터페이스를 활용한 직관적인 워크플로우 구축
**후처리 및 업스케일링 통합**: 생성된 이미지의 품질 향상을 위한 자동화된 후처리 과정 (예: Real-ESRGAN, Latent Upscale 등)

## 🛠️ 설치 및 시작하기

이 프로젝트를 로컬 환경에서 실행하기 위한 단계별 가이드입니다.

### 📋 전제 조건

* [cite_start]Python 3.12 [cite: 1]
* * [cite_start]CUDA 12.8, Pytourch 2.7.1 (pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128)
* [cite_start]Git (저장소를 클론하기 위해 필요) [cite: 1]
* [cite_start]NVIDIA GPU (CUDA 지원, ComfyUI 실행을 위해 필수) [cite: 1]


### ⬇️ 설치 단계

1. **Git 저장소 클론**:
   먼저 이 저장소를 로컬 컴퓨터에 복제합니다.
   
   ```bash
   git clone [https://github.com/90cube/Nicediffusion.git](https://github.com/90cube/Nicediffusion.git)
   cd Nicediffusion
   ```
   
   * `git clone`: 원격 저장소를 로컬로 복제.
   * `cd Nicediffusion`: 복제된 디렉토리로 이동.

2. **Python 가상 환경 설정 및 종속성 설치**:
   프로젝트에 필요한 파이썬 패키지들을 설치하고 가상 환경을 설정합니다.
   
   ```bash
   python -m venv venv
   .\venv\Scripts\activate # Windows
   # source venv/bin/activate # Linux
   
   # Windows 환경을 위한 라이브러리 설치
   pip install -r requirements_win.txt
   
   # PyTorch 설치 (CUDA 12.8용, GPU 환경에 맞춰 확인)
   pip install torch torchvision torchaudio --index-url [https://download.pytorch.org/whl/cu128](https://download.pytorch.org/whl/cu128)
   ```

## 💡 사용법

NiceDiffusion은 자체 UI를 통해 이미지 생성 작업을 관리합니다.

1. **NiceDiffusion 앱 실행**:
   `Nicediffusion` 프로젝트의 루트 디렉토리에서 다음 명령어를 실행합니다. 가상 환경이 활성화되어 있는지 확인하세요.
   
   ```bash
   python main.py
   ```

2. 웹 브라우저에서 `http://localhost:8080` (또는 콘솔에 표시되는 주소)으로 접속하여 NiceDiffusion UI에 접근합니다.

3. UI에서 모델을 선택하고, 프롬프트와 기타 설정을 조정한 후 "생성" 버튼을 클릭하여 이미지를 생성합니다.
   
   
   
   
   # NiceDiffusion 개발 로드맵
   
   ## 📋 Phase 1: 기본 기능 구현 (현재 완료 단계)
   
   - ✅ NiceGUI 기반 UI 구성
   - ✅ Diffusers 파이프라인 통합
   - ✅ 모델 로딩 시스템
   - ✅ 기본 이미지 생성 (txt2img)
   - ✅ 파라미터 조정 UI
   - ✅ 메타데이터 추출 및 표시
   - ✅ 프롬프트 프리셋 시스템
   - ✅ 배치 생성
   - ✅ 반복 생성
   - ⏳ 에러 처리 개선

   ## 📋 Phase 1 : 기본 기능 강화 및 클래스별 .py 생성
   
   
   ## 🚀 Phase 2: 고급 기능 구현
   
   ### 2A: 추가 생성 모드
   
   - [ ] img2img 구현
   - [ ] inpaint/outpaint 구현
   - [ ] ControlNet 통합
   - [ ] IP-Adapter 지원
   
   ### 2B: 캔버스 에디터
   
   - [ ] HTML5 Canvas 기반 편집 도구
   - [ ] 레이어 시스템
   - [ ] 마스크 편집
   - [ ] 실시간 미리보기
   
   ### 2C: 고급 기능
   
   - [ ] 히스토리 관리 및 복원
   - [ ] 프롬프트 믹싱
   - [ ] Seed 여행 (interpolation)
   
   ## 🔧 Phase 3: 확장성 및 통합
   
   ### 3A: 플러그인 시스템
   
   ```python
   # 플러그인 구조 예시
   plugins/
   ├── __init__.py
   ├── base.py           # 플러그인 베이스 클래스
   ├── prompt_helper/    # LLM 프롬프트 도우미
   ├── style_transfer/   # 스타일 전송
   └── batch_processor/  # 배치 처리
   ```
   
   ### 3B: ComfyUI 통합
   
   - [ ] ComfyUI 워크플로우 임포트
   - [ ] 노드 에디터 UI
   - [ ] 커스텀 노드 지원
   - [ ] 워크플로우 저장/불러오기
   
   ### 3C: 외부 서비스 연동
   
   - [ ] Civitai API 연동 (모델 다운로드)
   - [ ] HuggingFace 연동
   - [ ] 클라우드 저장소 지원
   - [ ] Discord/Telegram 봇
   
   ## 🎯 Phase 4: 엔터프라이즈 기능
   
   - [ ] 멀티 유저 지원
   - [ ] 작업 큐 시스템
   - [ ] GPU 클러스터 지원
   - [ ] REST API 서버
   - [ ] 웹 기반 배포
   
   ## 🛠️ 기술 스택 진화
   
   ### 현재 (Phase 1)
   
   - Frontend: NiceGUI
   - Backend: Diffusers, PyTorch
   - Storage: 로컬 파일 시스템
   
   ### 미래 (Phase 3-4)
   
   - Frontend: NiceGUI + React 컴포넌트
   - Backend: FastAPI + Celery
   - Storage: S3 호환 스토리지
   - Database: PostgreSQL/SQLite
   - Cache: Redis
   
   ## 📊 성능 목표
   
   - Phase 1: 단일 GPU, 512x512 이미지 5초 이내
   - Phase 2: 멀티 해상도, 실시간 미리보기
   - Phase 3: 배치 처리, 병렬 생성
   - Phase 4: 분산 처리, 무제한 확장
   
   ## 🔌 플러그인 예시
   
   ```python
   # plugins/prompt_helper/main.py
   from nicediff.core.plugin_base import PluginBase
   
   class PromptHelperPlugin(PluginBase):
       name = "Prompt Helper"
       version = "1.0.0"
   
       def __init__(self, state_manager):
           super().__init__(state_manager)
           self.llm_client = None
   
       def register(self):
           # UI에 버튼 추가
           self.state.subscribe('ui_ready', self.add_ui_elements)
   
       def enhance_prompt(self, prompt: str) -> str:
           # LLM을 사용해 프롬프트 개선
           return enhanced_prompt
   ```

## 최종 폴더 구조
nicediffusion/
├── .gitignore
├── README.md
├── requirements.txt
├── config.toml
├── install.py
├── run.py
│
├── assets/
│   ├── css/
│   │   └── main.css
│   └── images/
│       └── logo.png
│
├── plugins/
│   ├── README.md
│   │
│   ├── third_party_sampler/
│   │   ├── __init__.py
│   │   ├── plugin.yaml
│   │   ├── main.py
│   │   └── requirements.txt
│   │
│   └── imgur_uploader/
│       ├── __init__.py
│       ├── plugin.yaml
│       └── main.py
│
└── src/
    └── nicediff/
        ├── __init__.py
        ├── main.py
        │
        ├── core/
        │   ├── __init__.py
        │   ├── plugin_manager.py
        │   ├── state_manager.py
        │   ├── logger.py
        │   └── error_handler.py
        │
        ├── services/
        │   ├── __init__.py
        │   ├── model_scanner.py
        │   ├── metadata_parser.py
        │   └── sampler_mapper.py
        │
        ├── image_pad/
        │   ├── __init__.py
        │   │
        │   ├── shared/
        │   │   ├── __init__.py
        │   │   └── zoom_controls.py
        │   │
        │   └── modes/
        │       ├── __init__.py
        │       ├── txt2img/
        │       │   └── ui.py
        │       ├── img2img/
        │       │   └── ui.py
        │       ├── inpaint/
        │       │   ├── ui.py
        │       │   └── web/
        │       │       └── inpaint_canvas.js
        │       ├── upscale/
        │       │   └── ui.py
        │       └── pose_editor/
        │           ├── ui.py
        │           └── web/
        │               └── pose_editor_main.js
        │
        ├── ui/
        │   ├── __init__.py
        │   ├── workspace.py
        │   └── theme.py
        │
        ├── components/
        │   ├── __init__.py
        │   │
        │   ├── layout/
        │   │   ├── __init__.py
        │   │   ├── top_bar.py
        │   │   └── utility_sidebar.py
        │   │
        │   ├── sidebar_modules/
        │   │   ├── __init__.py
        │   │   ├── history_panel.py
        │   │   ├── generation_mode_selector.py
        │   │   ├── drawing_tools_panel.py
        │   │   └── edit_tools_panel.py
        │   │
        │   ├── panels/
        │   │   ├── __init__.py
        │   │   ├── parameter_panel.py
        │   │   ├── prompt_panel.py
        │   │   ├── lora_panel.py
        │   │   └── metadata_panel.py
        │   │
        │   ├── controls/
        │   │   ├── __init__.py
        │   │   ├── sampler_controls.py
        │   │   ├── quality_controls.py
        │   │   └── memory_controls.py
        │   │
        │   └── global_widgets/
        │       ├── __init__.py
        │       ├── notification.py
        │       └── modal.py
        │
        └── utils/
            ├── __init__.py
            ├── file_utils.py
            └── image_utils.py

## 🤝 기여 방법

[cite_start]이 프로젝트는 오픈 소스로 운영되며, 여러분의 기여를 환영합니다! [cite: 1]

1. [cite_start]저장소를 Fork 합니다. [cite: 1]
2. [cite_start]새로운 기능 브랜치를 생성합니다 (`git checkout -b feature/AmazingFeature`). [cite: 1]
3. [cite_start]변경 사항을 커밋합니다 (`git commit -m 'Add some AmazingFeature'`). [cite: 1]
4. [cite_start]브랜치를 원격 저장소로 푸시합니다 (`git push origin feature/AmazingFeature`). [cite: 1]
5. [cite_start]Pull Request를 생성합니다. [cite: 1]

## 📄 라이선스

이 프로젝트는 MIT 라이선스에 따라 배포됩니다. [cite_start]자세한 내용은 `LICENSE` 파일을 참조하세요. [cite: 1]

## 📧 문의

* [cite_start]카카오톡 오픈채팅: "[카카오톡 오픈채팅](https://open.kakao.com/o/gEnuCiFh)" [cite: 1]
* [cite_start]입장 코드: "cube" [cite: 1]

---
