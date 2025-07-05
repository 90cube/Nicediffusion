# Nicediffusion

![aidraw_simple_flat_logo_--ar_1716_--profile_5h5ugbf_--dref_ht_a5ab635c-b51a-4c00-a63c-383b2a766d5f_3](https://github.com/user-attachments/assets/3e8f7682-e14d-4566-a1d1-3d4f91b9eb0d)

# NiceDiffusion - ComfyUI 기반의 이미지 생성 자동화 워크플로우

## ✨ 프로젝트 소개

**NiceDiffusion**은 AI 이미지 생성 도구인 [ComfyUI](https://github.com/comfyanonymous/ComfyUI)를 기반으로 하여, 더욱 효율적이고 사용자 친화적인 이미지 생성 및 자동화 워크플로우를 제공하기 위해 개발되었습니다. 게임 컨셉 아트, 시각 개발, 다양한 창작 작업에 필요한 고품질 이미지를 빠르고 일관되게 생성하는 것을 목표로 합니다.

이 프로젝트는 단순히 이미지를 생성하는 것을 넘어, ComfyUI의 유연한 노드 기반 시스템을 활용하여 복잡한 워크플로우를 자동화하고, 사용자가 최소한의 노력으로 최대의 결과물을 얻을 수 있도록 돕습니다. 특히 반복적인 작업이나 대량의 이미지 생성이 필요한 경우에 진가를 발휘합니다.

## 🚀 주요 기능

* [cite_start]**다양한 Diffusion 모델 지원**: SDXL, SD1.5 등 여러 Stable Diffusion 모델과 커스텀 체크포인트 지원 [cite: 1]
* [cite_start]**고도화된 프롬프트 관리**: T5 CLIP 기반 프롬프트 또는 WD Tagger 기반 태그를 활용한 정확한 이미지 제어 [cite: 1]
* [cite_start]**ComfyUI 워크플로우 자동화**: 특정 조건에 따른 이미지 생성 파이프라인 자동 실행 (예: 특정 프롬프트 리스트 기반 배치 생성) [cite: 1]
* [cite_start]**파라미터 스위칭 및 실험**: 이미지 생성 파라미터(CFG, Step 등)를 쉽게 변경하고 비교하는 기능 [cite: 1]
* [cite_start]**시각적 워크플로우 편집**: ComfyUI의 강력한 노드 기반 인터페이스를 활용한 직관적인 워크플로우 구축 [cite: 1]
* [cite_start]**후처리 및 업스케일링 통합**: 생성된 이미지의 품질 향상을 위한 자동화된 후처리 과정 (예: Real-ESRGAN, Latent Upscale 등) [cite: 1]

## 🛠️ 설치 및 시작하기

이 프로젝트를 로컬 환경에서 실행하기 위한 단계별 가이드입니다.

### 📋 전제 조건

* [cite_start]Python 3.12 [cite: 1]
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

3. **ComfyUI 설치 (선택 사항, 워크플로우 직접 로드를 원할 경우)**:
   NiceDiffusion은 ComfyUI를 백엔드로 사용하지만, 직접 ComfyUI UI를 사용할 필요는 없을 수 있습니다. 필요하다면 다음을 따르세요:
   
   * ComfyUI Git 저장소를 NiceDiffusion 폴더와 같은 상위 경로에 클론합니다:
     
     ```bash
     git clone [https://github.com/comfyanonymous/ComfyUI.git](https://github.com/comfyanonymous/ComfyUI.git) ../ComfyUI
     ```
   * ComfyUI의 Python 패키지를 설치합니다 (필요한 경우):
     
     ```bash
     cd ../ComfyUI
     pip install -r requirements.txt --extra-index-url [https://download.pytorch.org/whl/cu128](https://download.pytorch.org/whl/cu128)
     ```

4. **모델 파일 다운로드**:
   [cite_start]사용할 Stable Diffusion 모델 체크포인트(예: SDXL, SD1.5)를 `../ComfyUI/models/checkpoints/` 폴더에 다운로드하여 배치합니다. [cite: 1]
   
   * [cite_start][Civitai](https://civitai.com/) 또는 [Hugging Face](https://huggingface.co/)에서 모델을 다운로드할 수 있습니다. [cite: 1]

5. **커스텀 노드 설치 (선택 사항)**:
   워크플로우에 따라 특정 커스텀 노드가 필요할 수 있습니다. ComfyUI Manager를 통해 쉽게 설치할 수 있습니다. [cite_start]`../ComfyUI` 폴더에서 ComfyUI를 실행한 뒤 Manager 탭에서 필요한 노드를 설치합니다. [cite: 1]
   
   ```bash
   # ComfyUI 실행 (ComfyUI 폴더에서)
   python main.py
   ```

6. **NiceDiffusion 워크플로우 로드 (선택 사항, ComfyUI와 함께 사용 시)**:
   [cite_start]`nicediffusion` 저장소에 포함된 `.json` 워크플로우 파일을 ComfyUI에 로드하여 사용합니다. [cite: 1]
   
   * [cite_start]ComfyUI를 실행하고, `Load` 버튼을 통해 `nicediffusion/workflows/` 폴더 안에 있는 `.json` 파일을 불러옵니다. [cite: 1]
   * [cite_start](선택 사항) `nicediffusion/scripts/` 폴더에 있는 Python 스크립트들을 활용하여 자동화된 작업을 실행합니다. [cite: 1]

## 💡 사용법

NiceDiffusion은 자체 UI를 통해 이미지 생성 작업을 관리합니다.

1. **NiceDiffusion 앱 실행**:
   `Nicediffusion` 프로젝트의 루트 디렉토리에서 다음 명령어를 실행합니다. 가상 환경이 활성화되어 있는지 확인하세요.
   
   ```bash
   python main.py
   ```
2. 웹 브라우저에서 `http://localhost:8080` (또는 콘솔에 표시되는 주소)으로 접속하여 NiceDiffusion UI에 접근합니다.
3. UI에서 모델을 선택하고, 프롬프트와 기타 설정을 조정한 후 "생성" 버튼을 클릭하여 이미지를 생성합니다.

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
