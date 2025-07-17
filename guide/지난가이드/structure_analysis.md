# 현재 구조 분석 및 개선 제안 📋

## ✅ 현재 구조의 장점
1. **핵심 분리가 잘 됨**: core/, services/ 분리 완벽
2. **모델 관리 체계**: metadata_parser, model_scanner 등 핵심 서비스 구비
3. **확장성 고려**: plugins/ 폴더 준비됨
4. **데이터 관리**: models/, presets/, outputs/ 체계적

## ⚠️ 누락된 중요 요소들

### 1. UI 레이어가 완전히 빠짐! 🚨
현재 main.py에서 UI를 어떻게 구성하는지가 불분명합니다.

**필요한 추가 구조:**
```
src/nicediff/
├── ui/                           # 🖥️ UI 레이어 (완전 누락!)
│   ├── __init__.py
│   ├── pages/                    # 📄 페이지들
│   │   ├── __init__.py
│   │   └── inference_page.py     # 메인 추론 페이지
│   ├── components/               # 🧩 UI 컴포넌트들
│   │   ├── __init__.py
│   │   ├── top_bar.py           # 상단 모델 선택 바
│   │   ├── image_pad.py         # 중앙 이미지 뷰어
│   │   ├── utility_sidebar.py   # 좌측 사이드바
│   │   ├── prompt_panel.py      # 프롬프트 패널
│   │   ├── parameter_panel.py   # 파라미터 패널
│   │   ├── lora_panel.py        # LoRA 패널
│   │   └── metadata_panel.py    # 메타데이터 패널
│   └── base_component.py        # UI 컴포넌트 기반 클래스
```

### 2. 도메인 로직 부족 🔧
고급 생성 기능을 위한 domains/ 레이어가 없습니다.

**필요한 추가 구조:**
```
src/nicediff/
├── domains/                      # 💼 비즈니스 도메인 로직
│   ├── __init__.py
│   └── generation/               # 🎨 이미지 생성 도메인
│       ├── __init__.py
│       ├── modes/                # 생성 모드들
│       │   ├── __init__.py
│       │   ├── txt2img.py        # 텍스트→이미지
│       │   ├── img2img.py        # 이미지→이미지
│       │   └── upscale.py        # 업스케일
│       ├── processors/           # 전/후 처리기
│       │   ├── __init__.py
│       │   ├── adetailer/
│       │   ├── controlnet/
│       │   └── segmentation/
│       └── strategies/           # 복잡한 워크플로우
│           ├── __init__.py
│           ├── basic_strategy.py
│           └── hires_fix_strategy.py
```

### 3. 유틸리티 및 헬퍼 🛠️
공통 기능들을 위한 utils/ 필요합니다.

**필요한 추가:**
```
src/nicediff/
├── utils/                        # 🔧 유틸리티
│   ├── __init__.py
│   ├── file_utils.py            # 파일 처리 유틸
│   ├── image_utils.py           # 이미지 처리 유틸
│   └── config_loader.py         # 설정 로더
```

## 🎯 권장 최종 구조

### 완성된 src/nicediff/ 구조:
```
src/nicediff/
├── __init__.py
├── core/                         # 🧠 핵심 시스템 (현재 완료)
│   ├── __init__.py
│   ├── event_bus.py             ✅
│   ├── state_manager.py         ✅
│   ├── container.py             ✅
│   └── error_handler.py         # 추가 권장
├── services/                     # 🔧 서비스 레이어 (현재 완료)
│   ├── __init__.py
│   ├── model_service.py         ✅
│   ├── file_service.py          ✅
│   ├── generation_service.py    ✅
│   ├── model_scanner.py         ✅
│   ├── metadata_parser.py       ✅
│   └── sampler_mapper.py        # 추가 권장
├── domains/                      # 💼 도메인 로직 (신규 추가)
│   └── generation/
│       ├── modes/
│       ├── processors/
│       └── strategies/
├── ui/                          # 🖥️ UI 레이어 (신규 추가)
│   ├── pages/
│   ├── components/
│   └── base_component.py
└── utils/                       # 🛠️ 유틸리티 (신규 추가)
    ├── file_utils.py
    ├── image_utils.py
    └── config_loader.py
```

## 🚀 실행 계획

### Phase 1: UI 레이어 추가 (1-2시간)
```bash
# 1. UI 폴더 구조 생성
mkdir -p src/nicediff/ui/{pages,components}
touch src/nicediff/ui/__init__.py
touch src/nicediff/ui/pages/__init__.py  
touch src/nicediff/ui/components/__init__.py

# 2. 기본 파일들 생성 (빈 클래스라도)
touch src/nicediff/ui/pages/inference_page.py
touch src/nicediff/ui/components/{top_bar,image_pad,parameter_panel}.py
```

### Phase 2: 도메인 레이어 추가 (2-3시간)
```bash
# 도메인 구조 생성
mkdir -p src/nicediff/domains/generation/{modes,processors,strategies}
# __init__.py 파일들 생성...
```

### Phase 3: Utils 추가 (30분)
```bash
mkdir -p src/nicediff/utils
touch src/nicediff/utils/{__init__.py,file_utils.py,image_utils.py}
```

## 🤔 현재 main.py는 어떻게 UI를 처리하나요?

문서에서 봤을 때 현재 main.py가 InferencePage를 import하고 있는데:

```python
from src.nicediff.pages.inference_page import InferencePage
```

이것은 **src/nicediff/ui/pages/inference_page.py**에 있어야 맞습니다.

## 💡 즉시 해야 할 것

### 1. 현재 상태 확인
```bash
# 현재 UI 관련 파일들이 어디에 있는지 확인
find . -name "*.py" | grep -E "(page|component|panel|bar|pad)"
ls -la src/nicediff/
```

### 2. 빠진 폴더들 생성
```bash
mkdir -p src/nicediff/ui/{pages,components}
mkdir -p src/nicediff/domains/generation/{modes,processors,strategies}  
mkdir -p src/nicediff/utils

# __init__.py 파일들 생성
find src/nicediff -type d -exec touch {}/__init__.py \;
```

### 3. 기존 UI 파일들 이동
```bash
# 만약 현재 UI 파일들이 다른 곳에 있다면 이동
# mv existing_ui_files/* src/nicediff/ui/components/
```

## 📋 결론

**현재 구조는 85% 완성!** 하지만 **UI 레이어가 완전히 빠져있어서** 실제 앱이 실행되지 않을 것 같습니다.

가장 우선적으로:
1. **UI 폴더 구조 생성** (5분)
2. **기존 UI 파일들이 어디 있는지 확인** (10분)  
3. **적절한 위치로 이동/정리** (15분)

이것만 하면 기본 구조는 완벽해집니다! 🎯
