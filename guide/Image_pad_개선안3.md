# 이미지 워크플로우 전달 시스템 완전 구현 기획서

## 📋 프로젝트 개요

### 목표
기존 nicediff의 모드 전환 시스템을 **Image Pad 중심의 워크플로우 기반 시스템**으로 전면 개편하여 사용자의 창작 워크플로우를 자연스럽게 지원하는 시스템 구축

### 핵심 원칙
1. **프롬프트 기반 vs 이미지 기반** 모드의 근본적 차이 반영
2. **Image Pad만 동적 변경**, 파라미터 패널은 고정 유지
3. **창작 워크플로우 보호**: 의미 없는 역방향 전달 차단
4. **시각적 연결성**: 사용자가 워크플로우 방향을 직관적으로 이해

---

## 🎯 워크플로우 정의

### 기본 워크플로우
```
T2I (프롬프트→이미지) → I2I (이미지→이미지) → Inpaint (이미지+마스크→이미지) → Upscale (이미지→고해상도이미지)
        ↓                    ↗ ↔                    ↗ ↔                         ↗
      순방향               양방향                   양방향                    양방향
```

### 전달 규칙 매트릭스
| From \ To | T2I | I2I | Inpaint | Upscale |
|-----------|-----|-----|---------|---------|
| **T2I**   | -   | ✅  | ✅      | ✅      |
| **I2I**   | ❌  | -   | ✅      | ✅      |
| **Inpaint** | ❌  | ✅  | -       | ✅      |
| **Upscale** | ❌  | ✅  | ✅      | -       |

**차단 이유**: T2I는 프롬프트 기반이므로 이미지 정보를 받을 수 없음. 이미지→프롬프트 전환 시 기존 작업 손실.

---

## 🏗️ 시스템 아키텍처

### 1. 전체 구조 개요
```
┌─────────────────────────────────────────────────────────────┐
│                    NiceDiff Application                      │
├─────────────────────────────────────────────────────────────┤
│  TopBar (모델 선택)                                           │
├─────────────────────────────────────────────────────────────┤
│  ParameterPanel (고정)  │  ImagePad (동적)  │  UtilitySidebar │
│  • 프롬프트 입력        │  • 모드별 UI      │  • LoRA 패널    │
│  • 기본 파라미터        │  • 이미지 표시    │  • 메타데이터   │
│  • 모드 선택 버튼       │  • 워크플로우     │  • 히스토리     │
│  • 생성 버튼           │  • 전달 버튼      │               │
└─────────────────────────────────────────────────────────────┘
```

### 2. 핵심 컴포넌트
- **WorkflowManager**: 워크플로우 전달 로직 관리
- **ImagePadManager**: 모드별 UI 동적 로딩
- **ModeHandlers**: 각 모드별 전용 핸들러
- **StateManager**: 중앙 상태 관리 (확장)

---

## 🔧 핵심 구현 클래스

### 1. WorkflowManager
```python
# src/nicediff/core/workflow_manager.py
from typing import Dict, List, Optional, Any
from PIL import Image
import time
from dataclasses import dataclass, field
from enum import Enum

class WorkflowMode(Enum):
    """워크플로우 모드 정의"""
    TXT2IMG = "txt2img"
    IMG2IMG = "img2img"
    INPAINT = "inpaint"
    UPSCALE = "upscale"

@dataclass
class WorkflowStep:
    """워크플로우 단계 정보"""
    from_mode: WorkflowMode
    to_mode: WorkflowMode
    image: Image.Image
    timestamp: float
    parameters: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

class WorkflowManager:
    """워크플로우 전달 로직 관리"""
    
    def __init__(self, state_manager):
        self.state = state_manager
        self.workflow_history: List[WorkflowStep] = []
        self.current_step = 0
        
        # 전달 규칙 정의 (프롬프트 기반 vs 이미지 기반)
        self.transfer_rules = {
            WorkflowMode.TXT2IMG: {
                WorkflowMode.IMG2IMG,
                WorkflowMode.INPAINT,
                WorkflowMode.UPSCALE
            },
            WorkflowMode.IMG2IMG: {
                WorkflowMode.INPAINT,
                WorkflowMode.UPSCALE
            },
            WorkflowMode.INPAINT: {
                WorkflowMode.IMG2IMG,
                WorkflowMode.UPSCALE
            },
            WorkflowMode.UPSCALE: {
                WorkflowMode.IMG2IMG,
                WorkflowMode.INPAINT
            }
        }
    
    def can_transfer(self, from_mode: str, to_mode: str) -> bool:
        """모드 간 전달 가능 여부 확인"""
        try:
            from_enum = WorkflowMode(from_mode)
            to_enum = WorkflowMode(to_mode)
            return to_enum in self.transfer_rules.get(from_enum, set())
        except ValueError:
            return False
    
    def get_available_targets(self, current_mode: str) -> List[str]:
        """현재 모드에서 전달 가능한 대상 모드들"""
        try:
            mode_enum = WorkflowMode(current_mode)
            return [mode.value for mode in self.transfer_rules.get(mode_enum, set())]
        except ValueError:
            return []
    
    def transfer_image(self, image: Image.Image, from_mode: str, to_mode: str, 
                      parameters: Dict[str, Any] = None) -> bool:
        """이미지 전달 실행"""
        if not self.can_transfer(from_mode, to_mode):
            print(f"❌ 워크플로우 전달 불가: {from_mode} → {to_mode}")
            return False
        
        # 워크플로우 단계 생성
        step = WorkflowStep(
            from_mode=WorkflowMode(from_mode),
            to_mode=WorkflowMode(to_mode),
            image=image,
            timestamp=time.time(),
            parameters=parameters or {},
            metadata={
                'image_size': image.size,
                'image_mode': image.mode,
                'transfer_type': 'manual'
            }
        )
        
        # 히스토리에 추가
        self.workflow_history.append(step)
        self.current_step = len(self.workflow_history) - 1
        
        # 상태 업데이트
        self.state.set('current_mode', to_mode)
        self.state.set('init_image', image)
        self.state.set('workflow_history', self.workflow_history)
        self.state.set('current_workflow_step', self.current_step)
        
        # 모드별 스마트 파라미터 설정
        self._apply_smart_parameters(to_mode, image, parameters)
        
        # 이벤트 발생
        self.state._notify('workflow_transferred', {
            'from_mode': from_mode,
            'to_mode': to_mode,
            'image_size': image.size,
            'step_index': self.current_step
        })
        
        print(f"✅ 워크플로우 전달 성공: {from_mode} → {to_mode}")
        return True
    
    def _apply_smart_parameters(self, target_mode: str, image: Image.Image, 
                              user_params: Dict[str, Any] = None):
        """대상 모드에 맞는 스마트 파라미터 적용"""
        current_params = self.state.get('current_params')
        
        if target_mode == 'img2img':
            # 이미지 크기에 맞춰 파라미터 조정
            self.state.update_param('width', image.width)
            self.state.update_param('height', image.height)
            self.state.update_param('strength', 0.7)  # 적절한 기본값
            
        elif target_mode == 'inpaint':
            # 인페인팅용 최적화
            self.state.update_param('width', image.width)
            self.state.update_param('height', image.height)
            self.state.update_param('strength', 0.9)
            self.state.update_param('steps', max(25, current_params.steps))
            
        elif target_mode == 'upscale':
            # 업스케일용 최적화
            self.state.update_param('strength', 0.3)
            self.state.update_param('steps', min(15, current_params.steps))
        
        # 사용자 지정 파라미터 오버라이드
        if user_params:
            for key, value in user_params.items():
                self.state.update_param(key, value)
    
    def get_workflow_summary(self) -> Dict[str, Any]:
        """워크플로우 요약 정보"""
        if not self.workflow_history:
            return {'steps': 0, 'current_mode': 'txt2img'}
        
        return {
            'steps': len(self.workflow_history),
            'current_step': self.current_step,
            'current_mode': self.workflow_history[-1].to_mode.value if self.workflow_history else 'txt2img',
            'history': [
                {
                    'from': step.from_mode.value,
                    'to': step.to_mode.value,
                    'timestamp': step.timestamp,
                    'image_size': step.image.size
                } for step in self.workflow_history
            ]
        }
    
    def reset_workflow(self):
        """워크플로우 초기화"""
        self.workflow_history.clear()
        self.current_step = 0
        self.state.set('current_mode', 'txt2img')
        self.state.set('init_image', None)
        self.state.set('workflow_history', [])
        self.state.set('current_workflow_step', 0)
        
        print("🔄 워크플로우 초기화 완료")
```

### 2. ImagePadManager
```python
# src/nicediff/ui/image_pad/image_pad_manager.py
from typing import Dict, Any, Optional
from nicegui import ui
from PIL import Image
from abc import ABC, abstractmethod

class BaseModeHandler(ABC):
    """모드 핸들러 기본 클래스"""
    
    def __init__(self, state_manager, workflow_manager):
        self.state = state_manager
        self.workflow = workflow_manager
        self.mode_name = None
        self.container = None
    
    @abstractmethod
    def render(self, container) -> None:
        """모드별 UI 렌더링"""
        pass
    
    @abstractmethod
    def cleanup(self) -> None:
        """모드 종료 시 정리"""
        pass
    
    def create_transfer_buttons(self, image: Image.Image) -> None:
        """전달 버튼 생성"""
        if not image:
            return
        
        available_targets = self.workflow.get_available_targets(self.mode_name)
        
        if not available_targets:
            return
        
        with ui.card().classes('w-full mt-4 p-3 bg-gray-800'):
            ui.label('다음 단계로 전달').classes('text-sm font-medium text-blue-400 mb-2')
            
            with ui.row().classes('w-full gap-2 justify-center'):
                for target_mode in available_targets:
                    icon = self._get_mode_icon(target_mode)
                    label = self._get_mode_label(target_mode)
                    
                    ui.button(
                        icon=icon,
                        text=label,
                        on_click=lambda t=target_mode: self._execute_transfer(image, t)
                    ).props('outline color=blue size=sm').classes('flex-col')
    
    def _execute_transfer(self, image: Image.Image, target_mode: str):
        """전달 실행"""
        success = self.workflow.transfer_image(image, self.mode_name, target_mode)
        
        if success:
            ui.notify(f'{self._get_mode_label(target_mode)}로 전달되었습니다', 
                     type='positive')
        else:
            ui.notify('전달할 수 없습니다', type='warning')
    
    def _get_mode_icon(self, mode: str) -> str:
        """모드별 아이콘"""
        icons = {
            'txt2img': 'text_fields',
            'img2img': 'image',
            'inpaint': 'brush',
            'upscale': 'zoom_in'
        }
        return icons.get(mode, 'help')
    
    def _get_mode_label(self, mode: str) -> str:
        """모드별 레이블"""
        labels = {
            'txt2img': 'T2I',
            'img2img': 'I2I',
            'inpaint': 'Inpaint',
            'upscale': 'Upscale'
        }
        return labels.get(mode, 'Unknown')

class ImagePadManager:
    """Image Pad 동적 모드 관리"""
    
    def __init__(self, state_manager, workflow_manager):
        self.state = state_manager
        self.workflow = workflow_manager
        self.current_handler = None
        self.container = None
        
        # 모드 핸들러 등록
        self.mode_handlers = {
            'txt2img': Txt2ImgHandler(state_manager, workflow_manager),
            'img2img': Img2ImgHandler(state_manager, workflow_manager),
            'inpaint': InpaintHandler(state_manager, workflow_manager),
            'upscale': UpscaleHandler(state_manager, workflow_manager)
        }
        
        # 모드 변경 이벤트 구독
        self.state.on('mode_changed', self._on_mode_changed)
    
    def render(self, container) -> None:
        """Image Pad 렌더링"""
        self.container = container
        
        # 초기 모드 로드
        current_mode = self.state.get('current_mode', 'txt2img')
        self._switch_mode(current_mode)
    
    def _on_mode_changed(self, event_data: Dict[str, Any]):
        """모드 변경 이벤트 처리"""
        new_mode = event_data.get('mode')
        if new_mode:
            self._switch_mode(new_mode)
    
    def _switch_mode(self, mode: str):
        """모드 전환 실행"""
        if mode not in self.mode_handlers:
            print(f"❌ 알 수 없는 모드: {mode}")
            return
        
        # 이전 핸들러 정리
        if self.current_handler:
            self.current_handler.cleanup()
        
        # 컨테이너 초기화
        if self.container:
            self.container.clear()
        
        # 새 핸들러 로드
        self.current_handler = self.mode_handlers[mode]
        
        # 새 모드 UI 렌더링
        with self.container:
            self.current_handler.render(self.container)
        
        print(f"✅ Image Pad 모드 전환: {mode}")
```

### 3. 모드별 핸들러 구현

#### 3.1 Txt2ImgHandler
```python
# src/nicediff/ui/image_pad/handlers/txt2img_handler.py
from .base_handler import BaseModeHandler
from nicegui import ui
from PIL import Image
import base64
import io

class Txt2ImgHandler(BaseModeHandler):
    """텍스트→이미지 모드 핸들러"""
    
    def __init__(self, state_manager, workflow_manager):
        super().__init__(state_manager, workflow_manager)
        self.mode_name = 'txt2img'
        self.image_display = None
        self.status_label = None
    
    def render(self, container):
        """T2I 모드 UI 렌더링"""
        with ui.column().classes('w-full h-full'):
            # 헤더
            with ui.card().classes('w-full p-3 bg-gray-900'):
                with ui.row().classes('w-full justify-between items-center'):
                    ui.label('Text to Image').classes('text-lg font-bold text-blue-400')
                    ui.icon('text_fields').classes('text-blue-400 text-2xl')
            
            # 이미지 표시 영역
            self.image_display = ui.element('div').classes(
                'w-full flex-1 border-2 border-dashed border-gray-600 '
                'flex items-center justify-center bg-gray-800 rounded-lg'
            )
            
            # 상태 표시
            self.status_label = ui.label('생성 버튼을 클릭하여 이미지를 생성하세요').classes(
                'text-center text-gray-400 mt-2'
            )
            
            # 생성된 이미지 확인 및 전달 버튼 표시
            self._check_generated_images()
        
        # 생성 완료 이벤트 구독
        self.state.on('generation_completed', self._on_generation_completed)
    
    def _check_generated_images(self):
        """기존 생성된 이미지 확인"""
        generated_images = self.state.get('generated_images', [])
        if generated_images:
            self._display_images(generated_images)
    
    def _on_generation_completed(self, event_data):
        """생성 완료 이벤트 처리"""
        images = event_data.get('images', [])
        if images:
            self._display_images(images)
    
    def _display_images(self, images):
        """이미지 표시 및 전달 버튼 생성"""
        if not images:
            return
        
        # 이미지 표시 영역 업데이트
        self.image_display.clear()
        
        with self.image_display:
            if len(images) == 1:
                # 단일 이미지
                image = images[0]
                self._display_single_image(image)
            else:
                # 다중 이미지 그리드
                self._display_image_grid(images)
        
        # 상태 레이블 업데이트
        self.status_label.set_text(f'이미지 생성 완료 ({len(images)}장)')
        
        # 전달 버튼 생성
        self.create_transfer_buttons(images[0])  # 첫 번째 이미지로 전달
    
    def _display_single_image(self, image: Image.Image):
        """단일 이미지 표시"""
        # PIL Image를 base64로 변환
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()
        
        with ui.column().classes('w-full h-full items-center justify-center'):
            ui.image(f'data:image/png;base64,{img_str}').classes(
                'max-w-full max-h-full object-contain'
            )
            
            # 이미지 정보
            with ui.row().classes('mt-2 text-sm text-gray-400'):
                ui.label(f'크기: {image.size[0]}×{image.size[1]}')
                ui.label(f'모드: {image.mode}')
    
    def _display_image_grid(self, images):
        """다중 이미지 그리드 표시"""
        cols = 2 if len(images) <= 4 else 3
        
        with ui.grid(columns=cols).classes('w-full h-full gap-2'):
            for i, image in enumerate(images):
                with ui.card().classes('p-2'):
                    buffer = io.BytesIO()
                    image.save(buffer, format='PNG')
                    img_str = base64.b64encode(buffer.getvalue()).decode()
                    
                    ui.image(f'data:image/png;base64,{img_str}').classes(
                        'w-full h-32 object-cover'
                    )
                    ui.label(f'#{i+1}').classes('text-xs text-center')
    
    def cleanup(self):
        """정리"""
        if self.image_display:
            self.image_display.clear()
        
        # 이벤트 구독 해제
        self.state.off('generation_completed', self._on_generation_completed)
```

#### 3.2 Img2ImgHandler
```python
# src/nicediff/ui/image_pad/handlers/img2img_handler.py
from .base_handler import BaseModeHandler
from nicegui import ui
from PIL import Image
import base64
import io

class Img2ImgHandler(BaseModeHandler):
    """이미지→이미지 모드 핸들러"""
    
    def __init__(self, state_manager, workflow_manager):
        super().__init__(state_manager, workflow_manager)
        self.mode_name = 'img2img'
        self.upload_area = None
        self.original_display = None
        self.result_display = None
        self.strength_slider = None
    
    def render(self, container):
        """I2I 모드 UI 렌더링"""
        with ui.column().classes('w-full h-full'):
            # 헤더
            with ui.card().classes('w-full p-3 bg-gray-900'):
                with ui.row().classes('w-full justify-between items-center'):
                    ui.label('Image to Image').classes('text-lg font-bold text-green-400')
                    ui.icon('image').classes('text-green-400 text-2xl')
            
            # 상하 분할: 원본 이미지 | 결과 이미지
            with ui.splitter(value=50).classes('w-full flex-1') as splitter:
                with splitter.before:
                    self._create_original_section()
                
                with splitter.after:
                    self._create_result_section()
        
        # 초기 이미지 확인
        self._check_init_image()
        
        # 이벤트 구독
        self.state.on('generation_completed', self._on_generation_completed)
    
    def _create_original_section(self):
        """원본 이미지 섹션"""
        with ui.column().classes('w-full h-full p-2'):
            ui.label('원본 이미지').classes('text-sm font-medium text-gray-300 mb-2')
            
            # 업로드 영역
            self.upload_area = ui.element('div').classes(
                'w-full flex-1 border-2 border-dashed border-green-500 '
                'flex items-center justify-center bg-gray-800 rounded-lg'
            )
            
            with self.upload_area:
                with ui.column().classes('items-center'):
                    ui.icon('cloud_upload').classes('text-4xl text-green-400 mb-2')
                    ui.label('이미지를 업로드하거나 드래그하세요').classes('text-green-400')
                    
                    # 파일 업로드
                    ui.upload(
                        on_upload=self._handle_image_upload,
                        auto_upload=True,
                        multiple=False
                    ).props('accept=image/*').classes('mt-2')
            
            # Strength 컨트롤
            self._create_strength_controls()
    
    def _create_result_section(self):
        """결과 이미지 섹션"""
        with ui.column().classes('w-full h-full p-2'):
            ui.label('생성 결과').classes('text-sm font-medium text-gray-300 mb-2')
            
            self.result_display = ui.element('div').classes(
                'w-full flex-1 border-2 border-dashed border-gray-600 '
                'flex items-center justify-center bg-gray-800 rounded-lg'
            )
            
            with self.result_display:
                ui.label('생성 버튼을 클릭하여 결과를 확인하세요').classes(
                    'text-gray-400 text-center'
                )
    
    def _create_strength_controls(self):
        """Denoising Strength 컨트롤"""
        with ui.card().classes('w-full p-3 mt-2 bg-gray-900'):
            ui.label('Denoising Strength').classes('text-sm font-medium text-green-400 mb-2')
            
            current_params = self.state.get('current_params')
            strength = getattr(current_params, 'strength', 0.7)
            
            self.strength_slider = ui.slider(
                min=0.0, max=1.0, step=0.01, value=strength
            ).on('update:model-value', self._update_strength).classes('w-full')
            
            with ui.row().classes('w-full justify-between text-xs text-gray-400 mt-1'):
                ui.label('0.0 (원본 유지)')
                ui.label(f'{strength:.2f}')
                ui.label('1.0 (완전 새로 생성)')
    
    def _check_init_image(self):
        """초기 이미지 확인 및 표시"""
        init_image = self.state.get('init_image')
        if init_image:
            self._display_original_image(init_image)
    
    def _handle_image_upload(self, event):
        """이미지 업로드 처리"""
        if not event.content:
            return
        
        try:
            # 업로드된 이미지 처리
            image = Image.open(io.BytesIO(event.content))
            
            # 상태 업데이트
            self.state.set('init_image', image)
            self.state.set('init_image_path', event.name)
            
            # 이미지 표시
            self._display_original_image(image)
            
            # 이미지 크기에 맞춰 파라미터 자동 조정
            self.state.update_param('width', image.width)
            self.state.update_param('height', image.height)
            
            ui.notify('이미지가 업로드되었습니다', type='positive')
            
        except Exception as e:
            ui.notify(f'이미지 업로드 실패: {str(e)}', type='negative')
    
    def _display_original_image(self, image: Image.Image):
        """원본 이미지 표시"""
        self.upload_area.clear()
        
        with self.upload_area:
            # 이미지 표시
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            img_str = base64.b64encode(buffer.getvalue()).decode()
            
            with ui.column().classes('w-full h-full items-center justify-center'):
                ui.image(f'data:image/png;base64,{img_str}').classes(
                    'max-w-full max-h-full object-contain'
                )
                
                # 이미지 정보
                with ui.row().classes('mt-2 text-sm text-gray-400'):
                    ui.label(f'크기: {image.size[0]}×{image.size[1]}')
                    ui.label(f'모드: {image.mode}')
                
                # 새 이미지 업로드 버튼
                ui.button(
                    '다른 이미지 선택',
                    icon='refresh',
                    on_click=self._reset_upload_area
                ).props('outline size=sm').classes('mt-2')
    
    def _reset_upload_area(self):
        """업로드 영역 초기화"""
        self.state.set('init_image', None)
        self.state.set('init_image_path', None)
        self.upload_area.clear()
        
        with self.upload_area:
            with ui.column().classes('items-center'):
                ui.icon('cloud_upload').classes('text-4xl text-green-400 mb-2')
                ui.label('이미지를 업로드하거나 드래그하세요').classes('text-green-400')
                
                ui.upload(
                    on_upload=self._handle_image_upload,
                    auto_upload=True,
                    multiple=False
                ).props('accept=image/*').classes('mt-2')
    
    def _update_strength(self, value):
        """Strength 값 업데이트"""
        self.state.update_param('strength', value)
        
        # 실시간 프리뷰 (옵션)
        if hasattr(self, 'strength_slider'):
            # 슬라이더 라벨 업데이트 등
            pass
    
    def _on_generation_completed(self, event_data):
        """생성 완료 이벤트 처리"""
        current_mode = self.state.get('current_mode')
        if current_mode != 'img2img':
            return
        
        images = event_data.get('images', [])
        if images:
            self._display_result_images(images)
    
    def _display_result_images(self, images):
        """결과 이미지 표시"""
        self.result_display.clear()
        
        with self.result_display:
            if len(images) == 1:
                # 단일 이미지
                image = images[0]
                buffer = io.BytesIO()
                image.save(buffer, format='PNG')
                img_str = base64.b64encode(buffer.getvalue()).decode()
                
                with ui.column().classes('w-full h-full items-center justify-center'):
                    ui.image(f'data:image/png;base64,{img_str}').classes(
                        'max-w-full max-h-full object-contain'
                    )
                    
                    # 이미지 정보
                    with ui.row().classes('mt-2 text-sm text-gray-400'):
                        ui.label(f'크기: {image.size[0]}×{image.size[1]}')
                        ui.label(f'모드: {image.mode}')
                
                # 전달 버튼 생성
                self.create_transfer_buttons(image)
            else:
                # 다중 이미지 처리
                self._display_result_grid(images)
    
    def _display_result_grid(self, images):
        """결과 이미지 그리드"""
        cols = 2 if len(images) <= 4 else 3
        
        with ui.grid(columns=cols).classes('w-full h-full gap-2'):
            for i, image in enumerate(images):
                with ui.card().classes('p-2'):
                    buffer = io.BytesIO()
                    image.save(buffer, format='PNG')
                    img_str = base64.b64encode(buffer.getvalue()).decode()
                    
                    ui.image(f'data:image/png;base64,{img_str}').classes(
                        'w-full h-32 object-cover'
                    )
                    ui.label(f'#{i+1}').classes('text-xs text-center')
        
        # 첫 번째 이미지로 전달 버튼
        if images:
            self.create_transfer_buttons(images[0])
    
    def cleanup(self):
        """정리"""
        if self.upload_area:
            self.upload_area.clear()
        if self.result_display:
            self.result_display.clear()
        
        # 이벤트 구독 해제
        self.state.off('generation_completed', self._on_generation_completed)
```

#### 3.3 InpaintHandler
```python
# src/nicediff/ui/image_pad/handlers/inpaint_handler.py
from .base_handler import BaseModeHandler
from nicegui import ui
from PIL import Image
import base64
import io

class InpaintHandler(BaseModeHandler):
    """인페인팅 모드 핸들러"""
    
    def __init__(self, state_manager, workflow_manager):
        super().__init__(state_manager, workflow_manager)
        self.mode_name = 'inpaint'
        self.canvas_container = None
        self.brush_size = 20
        self.brush_hardness = 0.8
        self.current_tool = 'brush'
    
    def render(self, container):
        """Inpaint 모드 UI 렌더링"""
        with ui.column().classes('w-full h-full'):
            # 헤더
            with ui.card().classes('w-full p-3 bg-gray-900'):
                with ui.row().classes('w-full justify-between items-center'):
                    ui.label('Inpaint').classes('text-lg font-bold text-purple-400')
                    ui.icon('brush').classes('text-purple-400 text-2xl')
            
            # 좌우 분할: 도구 패널 | 캔버스
            with ui.splitter(value=25).classes('w-full flex-1') as splitter:
                with splitter.before:
                    self._create_tool_panel()
                
                with splitter.after:
                    self._create_canvas_area()
        
        # 초기 이미지 확인
        self._check_init_image()
        
        # 이벤트 구독
        self.state.on('generation_completed', self._on_generation_completed)
    
    def _create_tool_panel(self):
        """도구 패널"""
        with ui.column().classes('w-full h-full p-2'):
            ui.label('도구').classes('text-sm font-medium text-purple-400 mb-2')
            
            # 브러시 도구
            with ui.card().classes('w-full p-3 mb-2 bg-gray-900'):
                ui.label('브러시').classes('text-xs font-medium text-gray-300 mb-2')
                
                # 도구 선택
                with ui.row().classes('w-full gap-1'):
                    ui.button('브러시', icon='brush', 
                             on_click=lambda: self._set_tool('brush')).props('size=sm')
                    ui.button('지우개', icon='cleaning_services',
                             on_click=lambda: self._set_tool('eraser')).props('size=sm')
                
                # 브러시 크기
                ui.label('크기').classes('text-xs text-gray-400 mt-2')
                ui.slider(min=1, max=100, step=1, value=self.brush_size,
                         on_change=self._set_brush_size).classes('w-full')
                
                # 브러시 경도
                ui.label('경도').classes('text-xs text-gray-400 mt-2')
                ui.slider(min=0.1, max=1.0, step=0.1, value=self.brush_hardness,
                         on_change=self._set_brush_hardness).classes('w-full')
            
            # 마스크 도구
            with ui.card().classes('w-full p-3 mb-2 bg-gray-900'):
                ui.label('마스크').classes('text-xs font-medium text-gray-300 mb-2')
                
                with ui.column().classes('w-full gap-1'):
                    ui.button('전체 선택', icon='select_all',
                             on_click=self._select_all).props('size=sm').classes('w-full')
                    ui.button('선택 해제', icon='clear',
                             on_click=self._clear_selection).props('size=sm').classes('w-full')
                    ui.button('선택 반전', icon='swap_vert',
                             on_click=self._invert_selection).props('size=sm').classes('w-full')
            
            # 실행 취소/다시 실행
            with ui.card().classes('w-full p-3 bg-gray-900'):
                ui.label('히스토리').classes('text-xs font-medium text-gray-300 mb-2')
                
                with ui.row().classes('w-full gap-1'):
                    ui.button('실행 취소', icon='undo',
                             on_click=self._undo).props('size=sm')
                    ui.button('다시 실행', icon='redo',
                             on_click=self._redo).props('size=sm')
    
    def _create_canvas_area(self):
        """캔버스 영역"""
        with ui.column().classes('w-full h-full p-2'):
            ui.label('캔버스').classes('text-sm font-medium text-gray-300 mb-2')
            
            # 캔버스 컨테이너
            self.canvas_container = ui.element('div').classes(
                'w-full flex-1 border border-purple-500 rounded-lg bg-gray-800 '
                'flex items-center justify-center'
            )
            
            with self.canvas_container:
                # HTML5 Canvas
                ui.html('''
                    <canvas id="inpaint-canvas" 
                            width="512" height="512"
                            style="max-width: 100%; max-height: 100%; border: 1px solid #666;">
                    </canvas>
                ''')
            
            # 캔버스 제어 버튼
            with ui.row().classes('w-full gap-2 mt-2'):
                ui.button('마스크 미리보기', icon='visibility',
                         on_click=self._toggle_mask_preview).props('size=sm')
                ui.button('마스크 저장', icon='save',
                         on_click=self._save_mask).props('size=sm')
                ui.button('마스크 로드', icon='folder_open',
                         on_click=self._load_mask).props('size=sm')
        
        # 캔버스 초기화
        self._init_canvas()
    
    def _init_canvas(self):
        """캔버스 초기화"""
        ui.run_javascript('''
            // 캔버스 초기화
            const canvas = document.getElementById('inpaint-canvas');
            if (canvas) {
                const ctx = canvas.getContext('2d');
                
                // 캔버스 매니저 연결
                if (window.canvasManager) {
                    window.canvasManager.switchMode('inpaint');
                    window.canvasManager.setBrushSize(20);
                    window.canvasManager.setBrushHardness(0.8);
                }
                
                // 체커보드 배경 그리기
                const drawCheckerboard = () => {
                    const size = 16;
                    ctx.fillStyle = '#404040';
                    ctx.fillRect(0, 0, canvas.width, canvas.height);
                    
                    ctx.fillStyle = '#606060';
                    for (let x = 0; x < canvas.width; x += size) {
                        for (let y = 0; y < canvas.height; y += size) {
                            if ((x / size + y / size) % 2 === 0) {
                                ctx.fillRect(x, y, size, size);
                            }
                        }
                    }
                };
                
                drawCheckerboard();
            }
        ''')
    
    def _check_init_image(self):
        """초기 이미지 확인"""
        init_image = self.state.get('init_image')
        if init_image:
            self._load_image_to_canvas(init_image)
    
    def _load_image_to_canvas(self, image: Image.Image):
        """이미지를 캔버스에 로드"""
        # 이미지를 base64로 변환
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()
        
        # JavaScript로 캔버스에 이미지 로드
        ui.run_javascript(f'''
            const canvas = document.getElementById('inpaint-canvas');
            const ctx = canvas.getContext('2d');
            const img = new Image();
            
            img.onload = function() {{
                // 캔버스 크기를 이미지에 맞게 조정
                canvas.width = img.width;
                canvas.height = img.height;
                
                // 이미지 그리기
                ctx.drawImage(img, 0, 0);
                
                // 캔버스 매니저에 이미지 등록
                if (window.canvasManager) {{
                    window.canvasManager.setBaseImage(img);
                }}
            }};
            
            img.src = 'data:image/png;base64,{img_str}';
        ''')
    
    def _set_tool(self, tool):
        """도구 변경"""
        self.current_tool = tool
        ui.run_javascript(f'''
            if (window.canvasManager) {{
                window.canvasManager.setTool('{tool}');
            }}
        ''')
    
    def _set_brush_size(self, size):
        """브러시 크기 변경"""
        self.brush_size = size
        ui.run_javascript(f'''
            if (window.canvasManager) {{
                window.canvasManager.setBrushSize({size});
            }}
        ''')
    
    def _set_brush_hardness(self, hardness):
        """브러시 경도 변경"""
        self.brush_hardness = hardness
        ui.run_javascript(f'''
            if (window.canvasManager) {{
                window.canvasManager.setBrushHardness({hardness});
            }}
        ''')
    
    def _select_all(self):
        """전체 선택"""
        ui.run_javascript('''
            if (window.canvasManager) {
                window.canvasManager.selectAll();
            }
        ''')
    
    def _clear_selection(self):
        """선택 해제"""
        ui.run_javascript('''
            if (window.canvasManager) {
                window.canvasManager.clearSelection();
            }
        ''')
    
    def _invert_selection(self):
        """선택 반전"""
        ui.run_javascript('''
            if (window.canvasManager) {
                window.canvasManager.invertSelection();
            }
        ''')
    
    def _undo(self):
        """실행 취소"""
        ui.run_javascript('''
            if (window.canvasManager) {
                window.canvasManager.undo();
            }
        ''')
    
    def _redo(self):
        """다시 실행"""
        ui.run_javascript('''
            if (window.canvasManager) {
                window.canvasManager.redo();
            }
        ''')
    
    def _toggle_mask_preview(self):
        """마스크 미리보기 토글"""
        ui.run_javascript('''
            if (window.canvasManager) {
                window.canvasManager.toggleMaskPreview();
            }
        ''')
    
    def _save_mask(self):
        """마스크 저장"""
        # JavaScript에서 마스크 데이터 가져오기
        ui.run_javascript('''
            if (window.canvasManager) {
                const maskData = window.canvasManager.getMaskData();
                // Python으로 마스크 데이터 전송
                window.pywebview.api.save_mask(maskData);
            }
        ''')
    
    def _load_mask(self):
        """마스크 로드"""
        # 파일 선택 다이얼로그 표시
        with ui.dialog() as dialog:
            with ui.card():
                ui.label('마스크 파일 선택')
                ui.upload(on_upload=self._handle_mask_upload, 
                         auto_upload=True).props('accept=image/*')
        dialog.open()
    
    def _handle_mask_upload(self, event):
        """마스크 업로드 처리"""
        if not event.content:
            return
        
        try:
            # 마스크 이미지 로드
            mask_image = Image.open(io.BytesIO(event.content))
            
            # 마스크를 캔버스에 적용
            buffer = io.BytesIO()
            mask_image.save(buffer, format='PNG')
            mask_str = base64.b64encode(buffer.getvalue()).decode()
            
            ui.run_javascript(f'''
                const maskImg = new Image();
                maskImg.onload = function() {{
                    if (window.canvasManager) {{
                        window.canvasManager.loadMask(maskImg);
                    }}
                }};
                maskImg.src = 'data:image/png;base64,{mask_str}';
            ''')
            
            ui.notify('마스크가 로드되었습니다', type='positive')
            
        except Exception as e:
            ui.notify(f'마스크 로드 실패: {str(e)}', type='negative')
    
    def _on_generation_completed(self, event_data):
        """생성 완료 이벤트 처리"""
        current_mode = self.state.get('current_mode')
        if current_mode != 'inpaint':
            return
        
        images = event_data.get('images', [])
        if images:
            # 결과 이미지 표시 및 전달 버튼 생성
            self._display_result_dialog(images)
    
    def _display_result_dialog(self, images):
        """결과 이미지 다이얼로그 표시"""
        with ui.dialog().props('maximized') as dialog:
            with ui.card().classes('w-full h-full'):
                with ui.row().classes('w-full justify-between items-center p-4'):
                    ui.label('인페인팅 결과').classes('text-lg font-bold')
                    ui.button(icon='close', on_click=dialog.close).props('flat round')
                
                with ui.row().classes('w-full flex-1 p-4'):
                    # 원본 이미지
                    with ui.column().classes('flex-1'):
                        ui.label('원본').classes('text-center font-medium mb-2')
                        init_image = self.state.get('init_image')
                        if init_image:
                            buffer = io.BytesIO()
                            init_image.save(buffer, format='PNG')
                            img_str = base64.b64encode(buffer.getvalue()).decode()
                            ui.image(f'data:image/png;base64,{img_str}').classes('w-full')
                    
                    # 결과 이미지
                    with ui.column().classes('flex-1'):
                        ui.label('결과').classes('text-center font-medium mb-2')
                        result_image = images[0]
                        buffer = io.BytesIO()
                        result_image.save(buffer, format='PNG')
                        img_str = base64.b64encode(buffer.getvalue()).decode()
                        ui.image(f'data:image/png;base64,{img_str}').classes('w-full')
                
                # 전달 버튼
                with ui.row().classes('w-full justify-center p-4'):
                    self.create_transfer_buttons(images[0])
        
        dialog.open()
    
    def cleanup(self):
        """정리"""
        if self.canvas_container:
            self.canvas_container.clear()
        
        # 캔버스 정리
        ui.run_javascript('''
            if (window.canvasManager) {
                window.canvasManager.cleanup();
            }
        ''')
        
        # 이벤트 구독 해제
        self.state.off('generation_completed', self._on_generation_completed)
```

#### 3.4 UpscaleHandler
```python
# src/nicediff/ui/image_pad/handlers/upscale_handler.py
from .base_handler import BaseModeHandler
from nicegui import ui
from PIL import Image
import base64
import io

class UpscaleHandler(BaseModeHandler):
    """업스케일 모드 핸들러"""
    
    def __init__(self, state_manager, workflow_manager):
        super().__init__(state_manager, workflow_manager)
        self.mode_name = 'upscale'
        self.scale_factor = 2.0
        self.upscale_method = 'lanczos'
    
    def render(self, container):
        """Upscale 모드 UI 렌더링"""
        with ui.column().classes('w-full h-full'):
            # 헤더
            with ui.card().classes('w-full p-3 bg-gray-900'):
                with ui.row().classes('w-full justify-between items-center'):
                    ui.label('Upscale').classes('text-lg font-bold text-orange-400')
                    ui.icon('zoom_in').classes('text-orange-400 text-2xl')
            
            # 좌우 분할: 설정 패널 | 이미지 비교
            with ui.splitter(value=25).classes('w-full flex-1') as splitter:
                with splitter.before:
                    self._create_settings_panel()
                
                with splitter.after:
                    self._create_comparison_area()
        
        # 초기 이미지 확인
        self._check_init_image()
        
        # 이벤트 구독
        self.state.on('generation_completed', self._on_generation_completed)
    
    def _create_settings_panel(self):
        """설정 패널"""
        with ui.column().classes('w-full h-full p-2'):
            ui.label('설정').classes('text-sm font-medium text-orange-400 mb-2')
            
            # 스케일 팩터
            with ui.card().classes('w-full p-3 mb-2 bg-gray-900'):
                ui.label('스케일 팩터').classes('text-xs font-medium text-gray-300 mb-2')
                ui.slider(min=1.0, max=8.0, step=0.5, value=self.scale_factor,
                         on_change=self._set_scale_factor).classes('w-full')
                ui.label(f'{self.scale_factor}x').classes('text-xs text-center text-gray-400')
            
            # 업스케일 방법
            with ui.card().classes('w-full p-3 mb-2 bg-gray-900'):
                ui.label('업스케일 방법').classes('text-xs font-medium text-gray-300 mb-2')
                ui.select(
                    options=['lanczos', 'bicubic', 'bilinear', 'nearest'],
                    value=self.upscale_method,
                    on_change=self._set_upscale_method
                ).classes('w-full')
            
            # 예상 결과 정보
            with ui.card().classes('w-full p-3 bg-gray-900'):
                ui.label('예상 결과').classes('text-xs font-medium text-gray-300 mb-2')
                
                init_image = self.state.get('init_image')
                if init_image:
                    original_size = init_image.size
                    new_width = int(original_size[0] * self.scale_factor)
                    new_height = int(original_size[1] * self.scale_factor)
                    
                    with ui.column().classes('w-full text-xs text-gray-400'):
                        ui.label(f'원본: {original_size[0]}×{original_size[1]}')
                        ui.label(f'결과: {new_width}×{new_height}')
                        ui.label(f'배율: {self.scale_factor}x')
                        
                        # 파일 크기 예상
                        original_pixels = original_size[0] * original_size[1]
                        new_pixels = new_width * new_height
                        size_ratio = new_pixels / original_pixels
                        ui.label(f'크기 증가: {size_ratio:.1f}x')
                else:
                    ui.label('이미지가 없습니다').classes('text-xs text-gray-400')
    
    def _create_comparison_area(self):
        """이미지 비교 영역"""
        with ui.column().classes('w-full h-full p-2'):
            ui.label('이미지 비교').classes('text-sm font-medium text-gray-300 mb-2')
            
            # 상하 분할: 원본 | 결과
            with ui.splitter(value=50, horizontal=False).classes('w-full flex-1') as splitter:
                with splitter.before:
                    self._create_original_view()
                
                with splitter.after:
                    self._create_result_view()
    
    def _create_original_view(self):
        """원본 이미지 뷰"""
        with ui.column().classes('w-full h-full'):
            ui.label('원본 이미지').classes('text-xs font-medium text-gray-400 mb-1')
            
            self.original_display = ui.element('div').classes(
                'w-full flex-1 border border-gray-600 rounded '
                'flex items-center justify-center bg-gray-800'
            )
            
            with self.original_display:
                ui.label('이미지를 로드하세요').classes('text-gray-400')
    
    def _create_result_view(self):
        """결과 이미지 뷰"""
        with ui.column().classes('w-full h-full'):
            ui.label('업스케일 결과').classes('text-xs font-medium text-gray-400 mb-1')
            
            self.result_display = ui.element('div').classes(
                'w-full flex-1 border border-gray-600 rounded '
                'flex items-center justify-center bg-gray-800'
            )
            
            with self.result_display:
                ui.label('생성 버튼을 클릭하세요').classes('text-gray-400')
    
    def _check_init_image(self):
        """초기 이미지 확인"""
        init_image = self.state.get('init_image')
        if init_image:
            self._display_original_image(init_image)
    
    def _display_original_image(self, image: Image.Image):
        """원본 이미지 표시"""
        self.original_display.clear()
        
        with self.original_display:
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            img_str = base64.b64encode(buffer.getvalue()).decode()
            
            with ui.column().classes('w-full h-full items-center justify-center'):
                ui.image(f'data:image/png;base64,{img_str}').classes(
                    'max-w-full max-h-full object-contain'
                )
                
                with ui.row().classes('mt-2 text-xs text-gray-400'):
                    ui.label(f'{image.size[0]}×{image.size[1]}')
                    ui.label(f'{image.mode}')
    
    def _set_scale_factor(self, factor):
        """스케일 팩터 설정"""
        self.scale_factor = factor
        
        # 파라미터 업데이트
        self.state.update_param('scale_factor', factor)
        
        # 예상 결과 업데이트
        self._update_expected_result()
    
    def _set_upscale_method(self, method):
        """업스케일 방법 설정"""
        self.upscale_method = method
        self.state.update_param('upscale_method', method)
    
    def _update_expected_result(self):
        """예상 결과 정보 업데이트"""
        # 설정 패널의 예상 결과 섹션 새로고침
        # 실제 구현에서는 해당 UI 요소만 업데이트
        pass
    
    def _on_generation_completed(self, event_data):
        """생성 완료 이벤트 처리"""
        current_mode = self.state.get('current_mode')
        if current_mode != 'upscale':
            return
        
        images = event_data.get('images', [])
        if images:
            self._display_result_image(images[0])
    
    def _display_result_image(self, image: Image.Image):
        """결과 이미지 표시"""
        self.result_display.clear()
        
        with self.result_display:
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            img_str = base64.b64encode(buffer.getvalue()).decode()
            
            with ui.column().classes('w-full h-full items-center justify-center'):
                ui.image(f'data:image/png;base64,{img_str}').classes(
                    'max-w-full max-h-full object-contain'
                )
                
                with ui.row().classes('mt-2 text-xs text-gray-400'):
                    ui.label(f'{image.size[0]}×{image.size[1]}')
                    ui.label(f'{image.mode}')
                    
                    # 스케일 팩터 표시
                    original_image = self.state.get('init_image')
                    if original_image:
                        actual_scale_x = image.size[0] / original_image.size[0]
                        actual_scale_y = image.size[1] / original_image.size[1]
                        ui.label(f'{actual_scale_x:.1f}x')
        
        # 전달 버튼 생성
        self.create_transfer_buttons(image)
    
    def cleanup(self):
        """정리"""
        if hasattr(self, 'original_display'):
            self.original_display.clear()
        if hasattr(self, 'result_display'):
            self.result_display.clear()
        
        # 이벤트 구독 해제
        self.state.off('generation_completed', self._on_generation_completed)
```

### 4. StateManager 확장
```python
# src/nicediff/core/state_manager.py (확장 부분)
class StateManager:
    """기존 StateManager에 워크플로우 지원 추가"""
    
    def __init__(self):
        super().__init__()
        self.workflow_manager = None  # 나중에 주입
        
        # 워크플로우 관련 상태 추가
        self._state.update({
            'workflow_history': [],
            'current_workflow_step': 0,
            'workflow_images': {},
            'workflow_enabled': True,
        })
    
    def set_workflow_manager(self, workflow_manager):
        """워크플로우 매니저 설정"""
        self.workflow_manager = workflow_manager
    
    def transfer_to_mode(self, target_mode: str, image: Image.Image = None, 
                        parameters: Dict[str, Any] = None) -> bool:
        """모드 전환과 이미지 전달"""
        if not self.workflow_manager:
            print("❌ 워크플로우 매니저가 설정되지 않았습니다")
            return False
        
        current_mode = self.get('current_mode', 'txt2img')
        
        # 이미지가 없으면 현재 생성된 이미지 사용
        if image is None:
            generated_images = self.get('generated_images', [])
            if generated_images:
                image = generated_images[0]
            else:
                print("❌ 전달할 이미지가 없습니다")
                return False
        
        # 워크플로우 매니저를 통해 전달
        return self.workflow_manager.transfer_image(
            image, current_mode, target_mode, parameters
        )
    
    def get_workflow_summary(self) -> Dict[str, Any]:
        """워크플로우 요약 정보"""
        if self.workflow_manager:
            return self.workflow_manager.get_workflow_summary()
        return {'steps': 0, 'current_mode': 'txt2img'}
    
    def reset_workflow(self):
        """워크플로우 초기화"""
        if self.workflow_manager:
            self.workflow_manager.reset_workflow()
```

### 5. 워크플로우 네비게이션 바
```python
# src/nicediff/ui/components/workflow_navigation.py
from nicegui import ui
from typing import Dict, Any

class WorkflowNavigationBar:
    """워크플로우 네비게이션 바"""
    
    def __init__(self, state_manager):
        self.state = state_manager
        self.workflow_manager = state_manager.workflow_manager
        self.mode_buttons = {}
    
    def render(self):
        """네비게이션 바 렌더링"""
        with ui.card().classes('w-full p-3 mb-4 bg-gray-900'):
            with ui.row().classes('w-full justify-center items-center gap-4'):
                self._create_mode_step('txt2img', 'T2I', 'text_fields', 'blue')
                self._create_arrow('→')
                self._create_mode_step('img2img', 'I2I', 'image', 'green')
                self._create_arrow('→')
                self._create_mode_step('inpaint', 'Inpaint', 'brush', 'purple')
                self._create_arrow('→')
                self._create_mode_step('upscale', 'Upscale', 'zoom_in', 'orange')
        
        # 워크플로우 변경 이벤트 구독
        self.state.on('workflow_transferred', self._on_workflow_changed)
        self.state.on('mode_changed', self._on_mode_changed)
    
    def _create_mode_step(self, mode: str, label: str, icon: str, color: str):
        """모드 단계 버튼 생성"""
        current_mode = self.state.get('current_mode', 'txt2img')
        workflow_history = self.state.get('workflow_history', [])
        
        # 상태 확인
        is_current = mode == current_mode
        has_been_visited = any(step['to_mode'] == mode for step in workflow_history)
        can_access = self._can_access_mode(mode)
        
        # 버튼 스타일 결정
        if is_current:
            btn_color = color
            btn_props = f'unelevated color={color}'
            border_class = f'border-2 border-{color}-500'
        elif has_been_visited:
            btn_color = 'positive'
            btn_props = f'outline color={color}'
            border_class = f'border-2 border-{color}-400'
        elif can_access:
            btn_color = 'grey-7'
            btn_props = 'outline color=grey-7'
            border_class = 'border-2 border-gray-500'
        else:
            btn_color = 'grey-9'
            btn_props = 'flat disable'
            border_class = 'border-2 border-gray-700'
        
        with ui.column().classes('items-center'):
            # 모드 버튼
            btn = ui.button(
                icon=icon,
                on_click=lambda m=mode: self._switch_to_mode(m) if can_access else None
            ).props(f'round size=lg {btn_props}').classes(f'{border_class} transition-all')
            
            self.mode_buttons[mode] = btn
            
            # 모드 레이블
            ui.label(label).classes('text-xs mt-1 font-medium')
            
            # 상태 표시
            status_text = ''
            if is_current:
                status_text = '현재'
                status_color = f'text-{color}-400'
            elif has_been_visited:
                status_text = '완료'
                status_color = 'text-green-400'
            elif can_access:
                status_text = '대기'
                status_color = 'text-gray-400'
            else:
                status_text = '잠김'
                status_color = 'text-gray-600'
            
            ui.label(status_text).classes(f'text-xs {status_color}')
    
    def _create_arrow(self, symbol: str):
        """화살표 생성"""
        ui.label(symbol).classes('text-2xl text-gray-400 font-bold')
    
    def _can_access_mode(self, target_mode: str) -> bool:
        """모드 접근 가능 여부"""
        current_mode = self.state.get('current_mode', 'txt2img')
        
        if not self.workflow_manager:
            return True
        
        # 현재 모드면 항상 접근 가능
        if target_mode == current_mode:
            return True
        
        # 워크플로우 규칙 확인
        return self.workflow_manager.can_transfer(current_mode, target_mode)
    
    def _switch_to_mode(self, target_mode: str):
        """모드 전환"""
        current_mode = self.state.get('current_mode', 'txt2img')
        
        if target_mode == current_mode:
            return
        
        if not self.workflow_manager:
            # 워크플로우 매니저가 없으면 단순 모드 전환
            self.state.set('current_mode', target_mode)
            return
        
        # 워크플로우 전달 가능 여부 확인
        if not self.workflow_manager.can_transfer(current_mode, target_mode):
            ui.notify(f'{current_mode}에서 {target_mode}로 직접 전환할 수 없습니다', 
                     type='warning')
            return
        
        # 이미지 전달과 함께 모드 전환
        generated_images = self.state.get('generated_images', [])
        if generated_images:
            success = self.state.transfer_to_mode(target_mode, generated_images[0])
            if success:
                ui.notify(f'{target_mode} 모드로 전환되었습니다', type='positive')
        else:
            # 이미지 없이 모드만 전환
            self.state.set('current_mode', target_mode)
            ui.notify(f'{target_mode} 모드로 전환되었습니다', type='info')
    
    def _on_workflow_changed(self, event_data: Dict[str, Any]):
        """워크플로우 변경 이벤트"""
        self._update_button_states()
    
    def _on_mode_changed(self, event_data: Dict[str, Any]):
        """모드 변경 이벤트"""
        self._update_button_states()
    
    def _update_button_states(self):
        """버튼 상태 업데이트"""
        current_mode = self.state.get('current_mode', 'txt2img')
        
        for mode, btn in self.mode_buttons.items():
            is_current = mode == current_mode
            can_access = self._can_access_mode(mode)
            
            if is_current:
                btn.props('unelevated')
            elif can_access:
                btn.props('outline')
            else:
                btn.props('flat disable')
```

### 6. 메인 애플리케이션 통합
```python
# src/nicediff/ui/main_interface.py (수정 부분)
from .components.workflow_navigation import WorkflowNavigationBar
from .image_pad.image_pad_manager import ImagePadManager
from ..core.workflow_manager import WorkflowManager

class MainInterface:
    """메인 인터페이스 (수정)"""
    
    def __init__(self, state_manager):
        self.state = state_manager
        
        # 워크플로우 매니저 생성 및 설정
        self.workflow_manager = WorkflowManager(state_manager)
        state_manager.set_workflow_manager(self.workflow_manager)
        
        # 컴포넌트 생성
        self.workflow_nav = WorkflowNavigationBar(state_manager)
        self.image_pad_manager = ImagePadManager(state_manager, self.workflow_manager)
    
    def render(self):
        """메인 인터페이스 렌더링"""
        with ui.column().classes('w-full h-screen'):
            # 상단 워크플로우 네비게이션
            self.workflow_nav.render()
            
            # 메인 컨텐츠 영역
            with ui.row().classes('w-full flex-1'):
                # 좌측 파라미터 패널 (고정)
                with ui.column().classes('w-80 h-full'):
                    self.parameter_panel.render()
                
                # 중앙 Image Pad (동적)
                with ui.column().classes('flex-1 h-full'):
                    self.image_pad_manager.render(ui.column().classes('w-full h-full'))
                
                # 우측 유틸리티 사이드바
                with ui.column().classes('w-80 h-full'):
                    self.utility_sidebar.render()
```

---

## 🚀 구현 로드맵

### Phase 1: 기본 구조 구축 (1주)
1. **WorkflowManager 클래스 구현**
   - 전달 규칙 정의
   - 이미지 전달 로직
   - 히스토리 관리

2. **ImagePadManager 기본 구조**
   - 모드별 핸들러 시스템
   - 동적 UI 로딩
   - 이벤트 연결

3. **BaseModeHandler 구현**
   - 공통 기능 정의
   - 전달 버튼 생성
   - 상태 관리 연결

### Phase 2: 모드별 핸들러 구현 (2주)
1. **Txt2ImgHandler**
   - 이미지 표시
   - 전달 버튼 생성
   - 다중 이미지 처리

2. **Img2ImgHandler**
   - 이미지 업로드
   - 비교 뷰어
   - Strength 컨트롤

3. **InpaintHandler**
   - Canvas 통합
   - 마스크 편집 도구
   - 결과 비교

4. **UpscaleHandler**
   - 설정 패널
   - 비교 뷰어
   - 실시간 프리뷰

### Phase 3: UI 통합 및 네비게이션 (1주)
1. **WorkflowNavigationBar**
   - 시각적 워크플로우 표시
   - 모드 전환 버튼
   - 상태 표시

2. **메인 인터페이스 통합**
   - 레이아웃 조정
   - 이벤트 연결
   - 상태 동기화

### Phase 4: 고급 기능 및 최적화 (1주)
1. **스마트 파라미터 전달**
   - 모드별 최적화
   - 자동 설정 조정
   - 사용자 커스터마이징

2. **워크플로우 템플릿**
   - 저장/로드 기능
   - 프리셋 관리
   - 공유 기능

3. **성능 최적화**
   - 이미지 캐싱
   - 메모리 관리
   - 렌더링 최적화

---

## 🎯 성공 지표

### 사용성 지표
- **모드 전환 시간**: 3초 이내
- **이미지 전달 성공률**: 99% 이상
- **사용자 오류율**: 워크플로우 방향 오류 0%

### 기능 지표
- **지원 이미지 형식**: PNG, JPEG, WebP
- **최대 이미지 크기**: 4K (3840×2160)
- **동시 처리 이미지**: 배치 크기만큼

### 성능 지표
- **메모리 사용량**: 현재 대비 +20% 이내
- **UI 반응성**: 100ms 이내
- **이미지 로딩 시간**: 1초 이내

---

## 🔧 설치 및 실행

### 의존성 추가
```bash
pip install pillow>=9.0.0
pip install nicegui>=1.4.0
```

### 파일 구조
```
src/nicediff/
├── core/
│   ├── workflow_manager.py        # 새로 추가
│   └── state_manager.py           # 확장
├── ui/
│   ├── components/
│   │   └── workflow_navigation.py # 새로 추가
│   ├── image_pad/
│   │   ├── image_pad_manager.py   # 새로 추가
│   │   └── handlers/              # 새로 추가
│   │       ├── __init__.py
│   │       ├── base_handler.py
│   │       ├── txt2img_handler.py
│   │       ├── img2img_handler.py
│   │       ├── inpaint_handler.py
│   │       └── upscale_handler.py
│   └── main_interface.py          # 수정
```

### 초기화 코드
```python
# src/nicediff/main.py
from nicegui import ui
from .core.state_manager import StateManager
from .ui.main_interface import MainInterface

def main():
    # 상태 관리자 초기화
    state_manager = StateManager()
    
    # 메인 인터페이스 생성
    main_interface = MainInterface(state_manager)
    
    # UI 렌더링
    main_interface.render()
    
    # 서버 시작
    ui.run(
        title='NiceDiff - Workflow Enhanced',
        port=8080,
        show=True
    )

if __name__ == "__main__":
    main()
```

---

## 🛠️ 커스터마이징 가이드

### 새로운 모드 추가
```python
# 1. 새로운 핸들러 클래스 생성
class CustomModeHandler(BaseModeHandler):
    def __init__(self, state_manager, workflow_manager):
        super().__init__(state_manager, workflow_manager)
        self.mode_name = 'custom_mode'
    
    def render(self, container):
        # 커스텀 UI 구현
        pass
    
    def cleanup(self):
        # 정리 로직
        pass

# 2. 워크플로우 규칙 추가
workflow_manager.transfer_rules[WorkflowMode.CUSTOM] = {
    WorkflowMode.IMG2IMG,
    WorkflowMode.UPSCALE
}

# 3. 핸들러 등록
image_pad_manager.mode_handlers['custom_mode'] = CustomModeHandler(
    state_manager, workflow_manager
)
```

### 커스텀 전달 규칙
```python
# 특별한 전달 규칙 추가
def custom_transfer_rule(from_mode: str, to_mode: str, image: Image.Image) -> bool:
    # 커스텀 조건 검사
    if from_mode == 'custom_mode' and to_mode == 'txt2img':
        # 특별한 경우에만 허용
        return image.size[0] > 1024
    
    return workflow_manager.can_transfer(from_mode, to_mode)

# 규칙 적용
workflow_manager.can_transfer = custom_transfer_rule
```

---

## 📝 마무리

이 기획서는 nicediff의 기존 구조를 최대한 활용하면서도 사용자 중심의 워크플로우 시스템을 구축하는 완전한 솔루션을 제시합니다. 

**핵심 가치:**
- ✅ **직관적 워크플로우**: 창작 과정을 자연스럽게 지원
- ✅ **의미 있는 제약**: 무의미한 역방향 전달 차단
- ✅ **확장성**: 새로운 모드 추가 용이
- ✅ **성능**: 기존 대비 최적화된 구조

구현 후 사용자는 T2I에서 시작하여 자연스럽게 I2I → Inpaint → Upscale로 이어지는 창작 워크플로우를 경험할 수 있으며, 필요에 따라 이미지 기반 모드 간 자유로운 이동이 가능합니다.