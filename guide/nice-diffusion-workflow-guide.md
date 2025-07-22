# Nice Diffusion 워크플로우 기반 Image Pad 구현 가이드

## 🎯 목적
각 모드별로 이미지를 유지하면서 정해진 워크플로우에 따라 이미지를 전송할 수 있는 시스템 구현

## 📋 워크플로우 규칙

| From Mode | To T2I | To I2I | To Inpaint | To Upscale |
|-----------|--------|--------|------------|------------|
| **T2I**   | -      | ✅     | ✅         | ✅         |
| **I2I**   | ❌     | -      | ✅         | ✅         |
| **Inpaint**| ❌    | ✅     | -          | ✅         |
| **Upscale**| ❌    | ✅     | ✅         | -          |

## 🛠️ 구현 코드

### 1. StateManager 확장
**파일**: `src/nicediff/core/state_manager.py` (추가 부분)

```python
def __init__(self):
    # 기존 초기화 코드...
    
    # 각 모드별 독립적인 이미지 상태
    self.mode_images = {
        'txt2img': None,
        'img2img': None,
        'inpaint': None,
        'upscale': None
    }
    
    # 워크플로우 규칙 정의
    self.workflow_rules = {
        'txt2img': ['img2img', 'inpaint', 'upscale'],
        'img2img': ['inpaint', 'upscale'],
        'inpaint': ['img2img', 'upscale'],
        'upscale': ['img2img', 'inpaint']
    }

def set_mode_image(self, mode: str, image):
    """특정 모드의 이미지 설정"""
    if mode in self.mode_images:
        self.mode_images[mode] = image
        self.emit(f'{mode}_image_changed', {'image': image})

def get_mode_image(self, mode: str):
    """특정 모드의 이미지 가져오기"""
    return self.mode_images.get(mode)

def get_allowed_transfers(self, from_mode: str):
    """허용된 전송 모드 목록 반환"""
    return self.workflow_rules.get(from_mode, [])
```

### 2. 개선된 ImagePad
**파일**: `src/nicediff/ui/image_viewer.py`

```python
"""
워크플로우 기반 이미지 패드
"""

from nicegui import ui
from pathlib import Path
from ..core.state_manager import StateManager
import asyncio
from PIL import Image
import numpy as np
import base64
import io

class ImagePad:
    """워크플로우 규칙을 따르는 이미지 패드"""
    
    def __init__(self, state_manager: StateManager):
        self.state = state_manager
        self.current_mode = 'txt2img'
        self.image_display = None
        self.upload_area = None
        self.status_label = None
        self.transfer_buttons = {}
        
        # 이벤트 구독
        self.state.subscribe('mode_changed', self._on_mode_changed)
        self.state.subscribe('generation_completed', self._on_generation_completed)
        self.state.subscribe('uploaded_image', self._on_uploaded_image_changed)
        
        # 각 모드별 이미지 변경 이벤트 구독
        for mode in ['txt2img', 'img2img', 'inpaint', 'upscale']:
            self.state.subscribe(f'{mode}_image_changed', self._on_mode_image_changed)
    
    async def render(self):
        """컴포넌트 렌더링"""
        with ui.column().classes('w-full h-full bg-gray-800 rounded-lg overflow-hidden relative') as main_container:
            self.main_container = main_container
            
            # 상단 도구바
            with ui.row().classes('absolute top-2 left-2 right-2 justify-between items-center z-10'):
                with ui.row().classes('items-center gap-2'):
                    ui.label('🖼️ 이미지 패드').classes('text-white bg-black bg-opacity-50 px-3 py-1 rounded text-sm font-bold')
                    self.mode_label = ui.label('').classes('text-yellow-400 bg-black bg-opacity-50 px-2 py-1 rounded text-xs')
                
                # 워크플로우 전송 버튼들
                with ui.row().classes('gap-2'):
                    self.transfer_button_container = ui.row().classes('gap-1')
                    ui.button(icon='refresh', on_click=self._refresh_image_pad).props('round size=sm')
            
            # 이미지 표시 영역
            self.image_container = ui.element('div').classes('w-full h-full flex items-center justify-center')
            with self.image_container:
                self.image_display = ui.element('div').classes('relative w-full h-full flex items-center justify-center')
            
            # 상태 표시
            with ui.row().classes('absolute bottom-2 right-2 z-10'):
                self.status_label = ui.label('준비됨').classes('text-white text-sm bg-gray-800 px-2 py-1 rounded')
        
        # 초기 표시
        await self._update_display()
    
    def _create_transfer_buttons(self):
        """현재 모드에 맞는 전송 버튼 생성"""
        self.transfer_button_container.clear()
        self.transfer_buttons.clear()
        
        with self.transfer_button_container:
            # 현재 모드에서 허용된 전송 목록
            allowed_transfers = self.state.get_allowed_transfers(self.current_mode)
            current_image = self.state.get_mode_image(self.current_mode)
            
            if current_image and allowed_transfers:
                ui.label('전송:').classes('text-white text-sm')
                
                for target_mode in allowed_transfers:
                    btn = ui.button(
                        self._get_mode_label(target_mode),
                        on_click=lambda m=target_mode: self._transfer_to_mode(m)
                    ).props('size=sm color=primary')
                    
                    # 아이콘 추가
                    if target_mode == 'img2img':
                        btn.props('icon=image')
                    elif target_mode == 'inpaint':
                        btn.props('icon=brush')
                    elif target_mode == 'upscale':
                        btn.props('icon=zoom_in')
                    
                    self.transfer_buttons[target_mode] = btn
    
    def _get_mode_label(self, mode: str) -> str:
        """모드 라벨 반환"""
        labels = {
            'txt2img': 'T2I',
            'img2img': 'I2I',
            'inpaint': 'Inpaint',
            'upscale': 'Upscale'
        }
        return labels.get(mode, mode)
    
    async def _update_display(self):
        """현재 모드의 이미지 표시"""
        if not self.image_display:
            return
        
        # 모드 라벨 업데이트
        if self.mode_label:
            self.mode_label.set_text(f'[{self._get_mode_label(self.current_mode)}]')
        
        # 전송 버튼 업데이트
        self._create_transfer_buttons()
        
        # 이미지 표시
        self.image_display.clear()
        
        with self.image_display:
            # 현재 모드의 이미지 가져오기
            current_image = self.state.get_mode_image(self.current_mode)
            
            if current_image:
                await self._show_image(current_image)
            else:
                await self._show_placeholder()
    
    async def _show_image(self, image):
        """이미지 표시"""
        try:
            # PIL Image를 base64로 변환
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            img_str = base64.b64encode(buffer.getvalue()).decode()
            
            # 체커보드 배경
            with ui.element('div').classes('absolute inset-0 bg-gray-700').style(
                'background-image: repeating-conic-gradient(#2a2a2a 0% 25%, #3a3a3a 0% 50%); '
                'background-position: 0 0, 10px 10px; '
                'background-size: 20px 20px;'
            ):
                pass
            
            # 이미지 표시
            img_element = ui.image(f'data:image/png;base64,{img_str}').classes(
                'relative z-10 max-w-full max-h-full object-contain drop-shadow-lg'
            ).style('width: auto; height: auto;')
            
            # 이미지 정보
            with ui.card().classes('absolute bottom-4 left-4 bg-black bg-opacity-70 text-white p-2 text-sm'):
                ui.label(f'{self._get_mode_label(self.current_mode)} | {image.width} × {image.height}px')
            
            # 상태 업데이트
            if self.status_label:
                self.status_label.set_text(f'{self._get_mode_label(self.current_mode)} 이미지')
                
        except Exception as e:
            print(f"❌ 이미지 표시 실패: {e}")
            ui.notify('이미지 표시 실패', type='negative')
    
    async def _show_placeholder(self):
        """플레이스홀더 표시"""
        with ui.card().classes('p-8 bg-gray-700'):
            if self.current_mode in ['img2img', 'inpaint', 'upscale']:
                # 업로드 영역
                ui.icon('cloud_upload', size='4em').classes('text-gray-400')
                ui.label('이미지를 업로드하거나 다른 모드에서 전송하세요').classes('text-gray-300 mt-2 text-center')
                
                self.upload_area = ui.upload(
                    on_upload=self._handle_upload,
                    auto_upload=True,
                    multiple=False
                ).props('accept=image/*').classes('mt-4')
                
                # 다른 모드에서 이미지 가져오기 힌트
                available_images = []
                for mode, image in self.state.mode_images.items():
                    if mode != self.current_mode and image is not None:
                        available_images.append(self._get_mode_label(mode))
                
                if available_images:
                    ui.label(f'사용 가능: {", ".join(available_images)}').classes('text-gray-400 text-xs mt-2')
            else:
                # T2I 모드
                ui.icon('brush', size='3em').classes('text-gray-400')
                ui.label('생성 버튼을 클릭하여 이미지를 생성하세요').classes('text-gray-300 mt-2')
    
    def _transfer_to_mode(self, target_mode: str):
        """다른 모드로 이미지 전송"""
        current_image = self.state.get_mode_image(self.current_mode)
        
        if current_image:
            print(f"🔄 이미지 전송: {self.current_mode} → {target_mode}")
            
            # 대상 모드에 이미지 설정
            self.state.set_mode_image(target_mode, current_image)
            self.state.set('init_image', current_image)
            
            # 모드 변경
            self.state.set('current_mode', target_mode)
            self.state.emit('mode_changed', {'mode': target_mode})
            
            ui.notify(f'{self._get_mode_label(target_mode)} 모드로 전환됨', type='success')
    
    async def _on_generation_completed(self, event_data):
        """생성 완료 이벤트 처리"""
        images = event_data.get('images', [])
        if images:
            current_mode = self.state.get('current_mode')
            print(f"✅ {current_mode}에서 이미지 생성 완료")
            
            # 현재 모드에 이미지 저장
            self.state.set_mode_image(current_mode, images[0])
    
    async def _on_mode_changed(self, data):
        """모드 변경 이벤트 처리"""
        new_mode = data.get('mode', 'txt2img') if isinstance(data, dict) else data
        self.current_mode = new_mode
        
        print(f"🔄 모드 변경됨: {new_mode}")
        
        # 표시 업데이트
        await self._update_display()
    
    async def _on_mode_image_changed(self, event_data):
        """특정 모드의 이미지 변경 시"""
        # 현재 모드의 이미지가 변경된 경우만 업데이트
        if hasattr(event_data, 'get'):
            mode = event_data.get('mode', '')
            if mode == self.current_mode:
                await self._update_display()
    
    async def _on_uploaded_image_changed(self, np_image):
        """업로드된 이미지 변경 시"""
        if np_image is not None:
            pil_image = Image.fromarray(np_image.astype('uint8'))
            
            # 현재 모드에 이미지 저장
            self.state.set_mode_image(self.current_mode, pil_image)
    
    async def _handle_upload(self, e):
        """파일 업로드 처리"""
        try:
            content = e.content.read()
            pil_image = Image.open(io.BytesIO(content))
            
            # 현재 모드에 이미지 저장
            self.state.set_mode_image(self.current_mode, pil_image)
            
            # init_image로도 설정
            self.state.set('init_image', pil_image)
            self.state.set('uploaded_image', np.array(pil_image))
            
            ui.notify(f'{self._get_mode_label(self.current_mode)}에 업로드 완료', type='positive')
            
        except Exception as ex:
            print(f"❌ 이미지 업로드 실패: {ex}")
            ui.notify('이미지 업로드 실패', type='negative')
    
    def _refresh_image_pad(self):
        """새로고침"""
        asyncio.create_task(self._update_display())
        ui.notify('새로고침 완료', type='info')
```

### 3. 모드 선택 UI 수정 (선택사항)
**파일**: `src/nicediff/ui/parameter_panel.py` (일부)

```python
def _create_mode_selector(self):
    """모드 선택기에 시각적 피드백 추가"""
    with ui.row().classes('w-full gap-2'):
        self.mode_buttons = {}
        
        for mode in ['txt2img', 'img2img', 'inpaint', 'upscale']:
            btn = ui.button(
                self._get_mode_label(mode),
                on_click=lambda m=mode: self._select_mode(m)
            ).props('flat')
            
            # 이미지가 있는 모드 표시
            if self.state.get_mode_image(mode):
                btn.props('color=positive')
                btn.tooltip(f'{self._get_mode_label(mode)}에 이미지 있음')
            
            self.mode_buttons[mode] = btn
    
    # 모드별 이미지 상태 변경 감지
    for mode in ['txt2img', 'img2img', 'inpaint', 'upscale']:
        self.state.subscribe(f'{mode}_image_changed', lambda: self._update_mode_buttons())

def _update_mode_buttons(self):
    """모드 버튼 상태 업데이트"""
    for mode, btn in self.mode_buttons.items():
        if self.state.get_mode_image(mode):
            btn.props('color=positive')
        else:
            btn.props('color=default')
```

## 📋 테스트 시나리오

1. **T2I 워크플로우**
   - T2I에서 이미지 생성
   - I2I, Inpaint, Upscale로 전송 확인
   - 각 모드에서 이미지 유지 확인

2. **역방향 차단**
   - I2I에서 T2I 전송 버튼이 없는지 확인
   - Inpaint에서 T2I 전송 버튼이 없는지 확인
   - Upscale에서 T2I 전송 버튼이 없는지 확인

3. **이미지 영속성**
   - 각 모드에서 이미지 생성/업로드
   - 다른 모드로 전환 후 다시 돌아와도 이미지 유지 확인

## ✅ 주요 특징

1. **독립적 이미지 상태**: 각 모드별로 이미지를 별도 저장
2. **워크플로우 규칙 적용**: 정해진 방향으로만 전송 가능
3. **시각적 피드백**: 이미지가 있는 모드 표시
4. **간편한 전송**: 버튼 클릭으로 즉시 전송

## 🎯 기대 효과

- 각 모드에서 작업한 이미지가 사라지지 않음
- 워크플로우에 따른 자연스러운 작업 흐름
- 명확한 UI로 사용자 혼란 방지
- 여러 이미지를 동시에 관리 가능