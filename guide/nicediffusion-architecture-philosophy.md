Nicediffusion 핵심 아키텍처 철학: 상세 가이드
1. 개요

이 문서는 Nicediffusion 프로젝트의 모든 코드가 따라야 할 근본적인 설계 원칙을 정의한다. 이 철학의 목표는 코드의 예측 가능성을 높이고, 유지보수를 용이하게 하며, 새로운 기능을 레고 블록처럼 쉽게 추가할 수 있는 유연한 구조를 만드는 것이다.
2. 세 가지 핵심 원칙

우리의 아키텍처는 다음 세 가지 원칙을 기둥으로 삼는다.

    계층적 모듈화 (Layered & Modular Architecture)

    중앙 집중식 상태 관리 (Centralized State Management)

    이벤트 기반 통신 (Event-Driven Communication)

3. 원칙 상세 설명
3.1. 계층적 모듈화: 각자의 역할에만 충실하라

모든 코드는 반드시 아래 3개의 계층 중 하나에 속해야 하며, 각 계층 간의 통신은 정해진 규칙을 따라야 한다.

    UI (사용자 인터페이스 계층)

        책임: 오직 사용자가 보고 상호작용하는 것에만 책임진다. 버튼, 슬라이더, 텍스트 입력 등 시각적 요소를 만들고 배치한다.

        규칙:

            절대 Core나 Services의 코드를 직접 호출해서는 안 된다.

            모든 '동작' 요청은 반드시 StateManager를 통해 이루어져야 한다. (예: state_manager.start_generation())

            화면에 표시될 데이터는 StateManager의 상태를 구독하여 가져온다.

    Services (전문 서비스 계층)

        책임: 파일 시스템 접근(모델 스캔, 이미지 저장), 외부 API 통신 등 특정 도메인에 얽매이지 않는 독립적인 '전문 기술'을 제공한다.

        규칙:

            UI나 Core의 존재를 알아서는 안 된다.

            필요한 모든 정보는 함수나 메소드의 인자(parameter)로 전달받아야 한다.

            자신의 작업 결과를 return 값으로 반환할 뿐, 다른 모듈의 상태를 직접 수정하지 않는다.

    Core (핵심 엔진 계층)

        책임: Nicediffusion의 가장 핵심적인 비즈니스 로직을 담는다. 이미지 생성 파이프라인, 상태 관리(StateManager), 모듈 간 통신(EventBus) 등이 여기에 속한다.

        규칙:

            가장 깊은 곳에 위치하며, 다른 모든 계층의 기반이 된다.

            UI 계층에 대한 어떠한 정보도 가져서는 안 된다.

3.2. 중앙 집중식 상태 관리: 진실은 오직 한 곳에 있다

StateManager는 우리 애플리케이션의 '뇌'이자 '중앙 관제탑'이다.

    진실의 원천 (Single Source of Truth):

        "현재 선택된 모델은 무엇인가?", "CFG 값은 몇인가?", "생성 중인가?" 와 같은 모든 앱의 '상태'는 오직 StateManager 안에만 존재해야 한다.

        다른 어떤 UI 컴포넌트나 서비스도 자신만의 독립적인 상태 값을 가져서는 안 된다.

    상태 변경 요청:

        UI 컴포넌트가 상태를 변경하고 싶을 때(예: 사용자가 슬라이더를 움직였을 때), UI는 자신의 값을 직접 바꾸는 것이 아니라, StateManager에게 "CFG 값을 7.5로 변경해줘" 라고 요청해야 한다.

        StateManager는 이 요청을 받아 자신의 상태를 업데이트하고, 이 변경 사항을 모든 구독자에게 알린다.

    구독과 반응 (Subscribe & React):

        모든 UI 컴포넌트는 StateManager의 특정 상태를 '구독'하고 있어야 한다.

        StateManager의 CFG 값이 7.5로 변경되면, 그 값을 구독하고 있던 모든 UI(예: 파라미터 패널의 숫자 표시, 히스토리의 CFG 값)는 이 변경을 통보받고 자신의 화면을 자동으로 업데이트한다.

        이를 통해 데이터의 흐름이 항상 UI -> StateManager -> UI로 예측 가능하게 흐른다.

3.3. 이벤트 기반 통신: 서로의 존재를 모른 채 협력하라

EventBus는 직접적인 관련이 없는 모듈 간의 통신을 위한 '방송 시스템'이다.

    언제 사용하는가?:

        상태의 '변경'이 아닌, 특정 '사건의 발생'을 알릴 때 사용한다.

        좋은 예: model_scan_completed, generation_failed, app_shutdown

        나쁜 예: cfg_slider_changed (이것은 상태 변경이므로 StateManager가 처리해야 한다.)

    동작 방식:

        발행 (Publish): ModelService가 모델 스캔을 완료하면, EventBus에 대고 "모델 스캔이 끝났어!" (model_scan_completed) 라고 외친다. 이때 ModelService는 누가 이 방송을 들을지 전혀 신경 쓰지 않는다.

        구독 (Subscribe): TopBar UI 컴포넌트는 미리 EventBus에 "나는 '모델 스캔 끝났다'는 방송이 나오면, 모델 목록 드롭다운을 새로고침할게" 라고 등록(구독)해 둔다.

        결과: ModelService와 TopBar는 서로의 코드를 한 줄도 import하지 않고도, EventBus라는 방송 시스템을 통해 완벽하게 협력하게 된다. 이를 통해 극단적인 수준의 **느슨한 결합(Loose Coupling)**이 완성된다.
