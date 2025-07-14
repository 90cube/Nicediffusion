# 2024-06-13 img2img UX 개선 시도 및 실패 내역

## 1. 시도 배경
- 기존 img2img 모드에서 이미지 업로드/상태관리/파이프라인 연동이 불안정하거나 UX가 직관적이지 않아 개선 필요성 제기
- JS 없이 업로드, tkinter/zenity 등 다양한 파일 선택 방식, 탭 기반 워크플로우(보기/편집/비교) 등 다양한 아이디어 실험

## 2. 주요 시도 내역

### (1) NiceGUI ui.upload만으로 업로드 이벤트 처리
- 업로드 이벤트가 감지되지 않거나, StateManager에 이미지가 제대로 저장되지 않는 문제 반복
- 드래그&드롭/클릭 모두 불안정

### (2) tkinter 파일 다이얼로그 방식
- 리눅스/윈도우/맥 모두 지원하려 했으나, 가상환경에서 tkinter 인식 문제 발생
- 시스템에 python3-tk 설치되어도 venv에서 import 오류 빈번
- zenity 대체도 시도했으나, 설치/호환성 미확인

### (3) 탭 기반(보기/편집/비교) 워크플로우 전체 덮어쓰기
- 기존 img2img 모드 전환/업로드/파이프라인 연동 등 핵심 로직이 덮어써져서 워크플로우가 꼬임
- NiceGUI slot 컨텍스트 에러 발생 (background task에서 UI 생성 시)
- txt2img 등 기본 모드 UX까지 복잡해짐

### (4) 기존 로직 + 고급 모드(탭) 병행 시도
- 기존 img2img 워크플로우 100% 유지, '고급 편집 모드' 버튼으로만 탭 진입하도록 분리
- 그러나 slot/context 문제, 함수 재사용 한계 등으로 완벽하게 분리 어려움

### (5) 최종적으로 git restore 및 원격 pull로 롤백
- 모든 실험적 변경사항 원복, v1.2 브랜치 최신 상태로 동기화

---

## 3. 문제점/교훈/주의사항
- **핵심 워크플로우(모드 전환, 업로드, StateManager 연동)는 절대 덮어쓰지 말 것**
- NiceGUI UI 생성은 반드시 메인 렌더링 컨텍스트에서만 할 것 (background task에서 UI 생성 금지)
- tkinter/zenity 등 외부 다이얼로그는 환경별 호환성, venv import 문제 반드시 사전 체크
- 새로운 UX(탭, 고급 편집 등)는 기존 함수/이벤트/상태관리 구조를 100% 재활용하는 방식으로만 점진적 도입
- 실험 전 반드시 git 브랜치/백업 필수

---

## 4. 다음 시도시 참고사항
- 기존 img2img 워크플로우(모드 전환, 업로드, StateManager 연동, 파이프라인 호출)는 건드리지 않고, UI만 점진적으로 확장할 것
- 고급 모드/탭 기반 UI는 별도 컨테이너에서만, 기존 함수만 재활용
- 파일 업로드/다이얼로그는 환경별 import/호환성 체크 코드부터 구현
- slot/context 문제 발생 시, 반드시 UI 생성 위치/컨텍스트부터 점검
- 실험 전 git 브랜치 분리/백업 필수

---

**실패 로그/교훈을 반드시 참고하여 내일은 안전하게 점진적 개선만 시도할 것!** 

---

## 5. [실전 적용 가이드] 모드 교체와 img2img 워크플로우 안전하게 확장하는 법

### 1) 기존 구조와 아이디어의 충돌 포인트
- 기존 ImagePad/StateManager/파이프라인은 'init_image' 또는 'working_image'를 기준으로 동작
- 모드 전환(UtilitySidebar 등에서 current_mode 변경) → StateManager/파라미터/UI가 연쇄적으로 동기화됨
- 새로운 탭 기반 워크플로우(보기/편집/비교)와 드래그앤드롭 업로드, 편집, 비교 등은 기존 업로드/상태관리/파이프라인 연동 함수와 반드시 호환되어야 함
- 기존 방식과 새로운 방식이 혼재되면 StateManager의 이미지 상태, 파라미터, 파이프라인 입력이 꼬일 수 있음

### 2) 실패/주의 사례
- 기존 모드 전환 로직(예: self.state.set('current_mode', method))이 여러 곳에서 중복 호출되면, StateManager의 상태가 꼬여서 이미지가 전달되지 않음
- 새로운 UI에서 이미지 업로드/편집 후 StateManager에 저장하는 방식이 기존 함수와 다르면 파이프라인에 이미지가 전달되지 않음
- 탭 기반 UI에서만 상태를 바꾸고, 기존 워크플로우와 연동하지 않으면 실제 생성 시 이미지 없음 오류 발생
- background task에서 UI를 그리거나, StateManager를 직접 조작하면 NiceGUI slot/context 에러 발생

### 3) 안전하게 적용하는 방법
- **모드 전환(UtilitySidebar 등)은 반드시 StateManager의 current_mode만 변경, 나머지 UI/상태는 기존 함수만 호출**
- **ImagePad 등에서 업로드/편집/비교 등 모든 상태 변화는 StateManager의 set('init_image') 또는 set('working_image')만 사용**
- **파이프라인 호출 시에도 StateManager에서만 이미지/파라미터를 읽어가도록 통일**
- **새로운 UI(탭, 드래그앤드롭 등)는 기존 업로드/상태관리/파이프라인 연동 함수만 재사용**
- **UI 컨텍스트(slot)는 반드시 메인 렌더링 함수에서만 생성**
- **실험 전 반드시 브랜치 분리/백업**

### 4) 실제 적용 예시
- UtilitySidebar에서 모드 전환 시: `self.state.set('current_mode', 'img2img')` → 기존 ImagePad/StateManager가 자동 동기화
- ImagePad에서 업로드/편집/비교 등 모든 상태 변화: `self.state.set('init_image', image)` 또는 `self.state.set('working_image', image)`
- 파이프라인 호출: `init_image = self.state.get('init_image')` 또는 `working_image = self.state.get('working_image')`
- 새로운 탭 기반 UI/드래그앤드롭 등은 기존 함수만 래핑해서 사용

### 5) 결론/교훈
- **핵심 워크플로우(모드 전환, 업로드, StateManager 연동, 파이프라인 호출)는 반드시 기존 함수/이벤트만 사용**
- **새로운 UI/UX는 기존 함수만 래핑해서 점진적으로 확장**
- **slot/context 문제, 상태 꼬임 방지에 항상 주의**

--- 