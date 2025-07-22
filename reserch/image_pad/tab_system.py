from ...core.logger import (
    debug, info, warning, error, success, failure, warning_emoji, 
    info_emoji, debug_emoji, process_emoji, model_emoji, image_emoji, ui_emoji, canvas_emoji
)
"""
Image Pad 탭 시스템 구현 - Fabric.js 통합 버전
Phase 1: Foundation & Unification에 따른 새로운 아키텍처
"""

from nicegui import ui
from abc import ABC, abstractmethod
from typing import Type, List, Dict, Any, Callable, Optional
import asyncio
import json
import io
import base64
from PIL import Image
import numpy as np
from ...core.state_manager import StateManager
from .utils.bridge import CanvasBridge

class JSBridge:
    """Python-JavaScript 통신 브릿지"""
    
    def __init__(self, tab_id: str):
        self.tab_id = tab_id
        self.callbacks = {}
    
    def send_to_js(self, command: str, data: Any = None):
        """JavaScript로 명령 전송"""
        js_code = f"""
        if (window.tabManager && window.tabManager.{self.tab_id}) {{
            window.tabManager.{self.tab_id}.{command}({json.dumps(data) if data else ''});
        }}
        """
        ui.run_javascript(js_code)
    
    def register_callback(self, event: str, callback: Callable):
        """JavaScript 이벤트 콜백 등록"""
        self.callbacks[event] = callback
        
        # JavaScript에서 Python으로 호출할 수 있도록 전역 함수 등록
        ui.run_javascript(f"""
        window.pyCallback_{self.tab_id}_{event} = function(data) {{
            fetch('/api/js-callback', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{
                    tab_id: '{self.tab_id}',
                    event: '{event}',
                    data: data
                }})
            }});
        }};
        """)
    
    def handle_js_callback(self, event: str, data: Any):
        """JavaScript 콜백 처리"""
        if event in self.callbacks:
            self.callbacks[event](data)

class BaseTab(ABC):
    """모든 탭의 기본 클래스 - Fabric.js 통합"""
    
    def __init__(self, state_manager: StateManager, tab_manager):
        self.state = state_manager
        self.tab_manager = tab_manager
        self.tab_id = None
        self.container = None
        self.canvas_id = None
        self.canvas_bridge = None
        self.is_active = False
        
        # JavaScript 통신 설정 (기존 호환성 유지)
        self.js_bridge = JSBridge(self.tab_id)
    
    def setup_canvas(self, canvas_id: str):
        """Fabric.js Canvas 설정"""
        self.canvas_id = canvas_id
        self.canvas_bridge = CanvasBridge(canvas_id)
        
        # Canvas 준비 이벤트 핸들러 등록
        self.canvas_bridge.register_event_handler('canvas_ready', self.on_canvas_ready)
        self.canvas_bridge.register_event_handler('image_loaded', self.on_image_loaded)
        self.canvas_bridge.register_event_handler('object_selected', self.on_object_selected)
        self.canvas_bridge.register_event_handler('object_modified', self.on_object_modified)
    
    def on_canvas_ready(self, data: Dict[str, Any]):
        """Canvas 준비 완료 이벤트"""
        success(f"{self.tab_id} Canvas 준비됨")
    
    def on_image_loaded(self, data: Dict[str, Any]):
        """이미지 로드 완료 이벤트"""
        image_emoji(f"{self.tab_id} 이미지 로드됨: {data.get('objectId')}")
    
    def on_object_selected(self, data: Dict[str, Any]):
        """객체 선택 이벤트"""
        info(f"🎯 {self.tab_id} 객체 선택됨: {data.get('objectId')}")
    
    def on_object_modified(self, data: Dict[str, Any]):
        """객체 수정 이벤트"""
        info(f"✏️ {self.tab_id} 객체 수정됨: {data.get('objectId')}")
    
    def load_image_to_canvas(self, image: Image.Image, options: Dict[str, Any] = None) -> bool:
        """이미지를 Canvas에 로드"""
        if self.canvas_bridge:
            return self.canvas_bridge.load_image(image, options)
        return False
    
    @abstractmethod
    def render(self, container) -> None:
        """탭 UI 렌더링"""
        pass
    
    @abstractmethod
    def activate(self) -> None:
        """탭 활성화"""
        pass
    
    @abstractmethod
    def cleanup(self) -> None:
        """탭 정리"""
        pass
    
    def create_transfer_buttons(self, image: Image) -> None:
        """전달 버튼 생성"""
        targets = self.tab_manager.get_transfer_targets(self.tab_id)
        
        if not targets:
            return
        
        with ui.card().classes('w-full mt-4 p-3 bg-gray-800'):
            ui.label('다른 탭으로 전달').classes('text-sm font-medium text-blue-400 mb-2')
            
            # 탭 아이콘 그리드
            with ui.grid(columns=4).classes('w-full gap-2'):
                for target in targets:
                    tab_info = self.get_tab_info(target)
                    
                    with ui.button(
                        icon=tab_info['icon'],
                        on_click=lambda t=target: self.transfer_to_tab(image, t)
                    ).props(f'flat square color={tab_info["color"]}').classes('h-12'):
                        ui.tooltip(tab_info['name'])
    
    def transfer_to_tab(self, image: Image, target_tab: str):
        """다른 탭으로 전달"""
        success = self.tab_manager.transfer_image(image, target_tab)
        
        if success:
            self.safe_notify(f'{self.get_tab_info(target_tab)["name"]}으로 전달됨', 'positive')
        else:
            self.safe_notify('전달할 수 없습니다', 'warning')
    
    def safe_notify(self, message: str, type: str = 'info'):
        """안전한 알림 표시 (부모 요소 삭제 오류 방지)"""
        try:
            ui.notify(message, type=type)
        except RuntimeError as e:
            if "parent element" in str(e) and "deleted" in str(e):
                warning_emoji(f"알림 표시 실패 (부모 요소 삭제됨): {message}")
            else:
                warning_emoji(f"알림 표시 실패: {e}")
        except Exception as e:
            warning_emoji(f"알림 표시 실패: {e}")
    
    def get_tab_info(self, tab_id: str) -> Dict[str, str]:
        """탭 정보 조회"""
        tab_infos = {
            'txt2img': {'name': 'Text to Image', 'icon': 'text_fields', 'color': 'blue'},
            'img2img': {'name': 'Image to Image', 'icon': 'image', 'color': 'green'},
            'inpaint': {'name': 'Inpaint', 'icon': 'brush', 'color': 'purple'},
            'upscale': {'name': 'Upscale', 'icon': 'zoom_in', 'color': 'orange'},
            '3d_pose': {'name': '3D Pose', 'icon': 'accessibility_new', 'color': 'red'},
            'mask_editor': {'name': 'Mask Editor', 'icon': 'layers', 'color': 'teal'},
            'sketch': {'name': 'Sketch', 'icon': 'draw', 'color': 'pink'},
        }
        return tab_infos.get(tab_id, {'name': 'Unknown', 'icon': 'help', 'color': 'grey'})

class Txt2ImgTab(BaseTab):
    """텍스트→이미지 탭"""
    
    def __init__(self, state_manager: StateManager, tab_manager):
        super().__init__(state_manager, tab_manager)
        self.tab_id = 'txt2img'
        self.result_display = None
        self.transfer_area = None
        
        # Fabric.js Canvas 설정
        self.setup_canvas(f'{self.tab_id}-canvas')
    
    def render(self, container):
        """T2I 탭 렌더링 - Fabric.js Canvas 사용"""
        self.container = container
        
        with container:
            # Fabric.js Canvas 컨테이너
            with ui.card().classes('w-full h-full min-h-[500px] bg-gray-800'):
                # Canvas 요소
                ui.element('canvas').classes('w-full h-full').props(f'id="{self.canvas_id}"')
                
                # 플레이스홀더 (Canvas 로드 전)
                with ui.element('div').classes('absolute inset-0 flex items-center justify-center bg-gray-800').props(f'id="{self.canvas_id}-placeholder"'):
                    with ui.column().classes('items-center justify-center'):
                        ui.icon('image', size='4em').classes('text-gray-500 mb-4')
                        ui.label('생성 버튼을 클릭하여 이미지를 만드세요').classes(
                            'text-gray-400 text-center text-lg mb-2'
                        )
                        ui.label('T2I 모드에서는 프롬프트를 입력하고 생성 버튼을 클릭하세요').classes(
                            'text-gray-500 text-center text-sm'
                        )
                
                # Canvas 초기화 스크립트
                ui.add_head_html(f'''
                    <script>
                        // Fabric.js 라이브러리 로드 확인 및 Canvas 초기화
                        function initCanvas_{self.canvas_id}() {{
                            if (typeof fabric !== 'undefined') {{
                                if (typeof createCanvasManager === 'function') {{
                                    createCanvasManager('{self.canvas_id}');
                                    console.log('✅ {self.tab_id} Canvas 매니저 생성됨');
                                    
                                    // 플레이스홀더 숨기기
                                    const placeholder = document.getElementById('{self.canvas_id}-placeholder');
                                    if (placeholder) {{
                                        placeholder.style.display = 'none';
                                    }}
                                }} else {{
                                    console.error('❌ createCanvasManager 함수를 찾을 수 없음');
                                }}
                            }} else {{
                                console.error('❌ Fabric.js 라이브러리가 로드되지 않음');
                                setTimeout(initCanvas_{self.canvas_id}, 100);
                            }}
                        }}
                        
                        // DOM 로드 완료 시 초기화
                        if (document.readyState === 'loading') {{
                            document.addEventListener('DOMContentLoaded', initCanvas_{self.canvas_id});
                        }} else {{
                            initCanvas_{self.canvas_id}();
                        }}
                    </script>
                ''')
            
            # 생성 완료 시 전달 버튼 영역
            self.transfer_area = ui.element('div').classes('w-full')
    
    def activate(self):
        """탭 활성화"""
        self.is_active = True
        self.state.set('current_mode', 'txt2img')
        
        # 생성 완료 이벤트 구독
        self.state.subscribe('generation_completed', self.on_generation_completed)
    
    def cleanup(self):
        """탭 정리"""
        self.is_active = False
        self.state.unsubscribe('generation_completed', self.on_generation_completed)
    
    def on_generation_completed(self, event_data):
        """생성 완료 이벤트 처리"""
        if not self.is_active:
            return
        
        images = event_data.get('images', [])
        if images:
            self.display_results(images)
    
    def display_results(self, images):
        """결과 이미지 표시 - Fabric.js Canvas 사용"""
        if not images:
            return
        
        # 첫 번째 이미지를 Canvas에 로드
        image = images[0]
        
        # Canvas 준비 대기 및 이미지 로드
        if self.canvas_bridge:
            # Canvas 준비 대기
            if self.canvas_bridge.wait_for_ready(timeout=5.0):
                success = self.load_image_to_canvas(image)
                if success:
                    success(f"{self.tab_id} 이미지 로드 성공")
                    # 전달 버튼 생성
                    self.create_transfer_buttons(image)
                else:
                    failure(f"{self.tab_id} 이미지 로드 실패")
            else:
                warning_emoji(f"{self.tab_id} Canvas 준비 시간 초과")
                # 폴백: 기존 방식으로 표시
                self._fallback_display(image)
        else:
            failure(f"{self.tab_id} Canvas Bridge가 초기화되지 않음")
            self._fallback_display(image)
    
    def _fallback_display(self, image):
        """Canvas 실패 시 폴백 표시"""
        if not self.container:
            return
        
        # 기존 내용 제거
        self.container.clear()
        
        # 이미지 최적화
        optimized_image = self.optimize_image_for_display(image)
        
        # Base64 변환
        buffer = io.BytesIO()
        optimized_image.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()
        
        with self.container:
            with ui.card().classes('w-full h-full flex flex-col bg-gray-800'):
                # 이미지 표시
                ui.image(f'data:image/png;base64,{img_str}').classes('w-full h-auto max-h-[80vh] object-contain')
                
                # 전달 버튼
                self.create_transfer_buttons(image)
        
        # 전달 버튼 생성
        if self.transfer_area:
            self.transfer_area.clear()
            with self.transfer_area:
                self.create_transfer_buttons(images[0])
    
    def display_single_image(self, image):
        """단일 이미지 표시 - Canvas 기반 Image Pad에 표시"""
        try:
            process_emoji(f"단일 이미지 표시 시작: {image.size}")
            
            # 원본 이미지를 base64로 변환
            buffer = io.BytesIO()
            image.save(buffer, format='PNG', optimize=True)
            img_str = base64.b64encode(buffer.getvalue()).decode()
            
            # Canvas 기반 Image Pad에 이미지 표시 (디버깅 강화)
            ui.run_javascript(f'''
                console.log('🔍 Canvas 매니저 상태 확인:');
                console.log('- window.imagePadCanvas:', window.imagePadCanvas);
                console.log('- window.imagePadCanvas?.loadImageFromBase64:', window.imagePadCanvas?.loadImageFromBase64);
                
                if (window.imagePadCanvas && window.imagePadCanvas.loadImageFromBase64) {{
                    console.log('🎨 Canvas에 이미지 로드 시작');
                    try {{
                        window.imagePadCanvas.loadImageFromBase64('data:image/png;base64,{img_str}');
                        console.log('✅ Canvas 이미지 로드 완료');
                    }} catch (error) {{
                        console.error('❌ Canvas 이미지 로드 실패:', error);
                    }}
                }} else {{
                    console.error('❌ Canvas 매니저를 찾을 수 없음');
                    console.log('🔄 Canvas 초기화 대기 중...');
                    
                    // Canvas 초기화 대기 후 재시도
                    setTimeout(() => {{
                        if (window.imagePadCanvas && window.imagePadCanvas.loadImageFromBase64) {{
                            console.log('🎨 Canvas 초기화 완료 - 이미지 로드 재시도');
                            window.imagePadCanvas.loadImageFromBase64('data:image/png;base64,{img_str}');
                        }} else {{
                            console.error('❌ Canvas 초기화 실패');
                        }}
                    }}, 1000);
                }}
            ''')
            
            # 이미지 정보만 표시 (Canvas 위에 오버레이)
            with ui.column().classes('w-full h-full items-center justify-center'):
                # 이미지 정보
                with ui.row().classes('mt-2 text-sm text-gray-400'):
                    ui.label(f'생성됨: {image.size[0]}×{image.size[1]}')
                    
            success(f"단일 이미지 표시 완료: {image.size}")
                    
        except Exception as e:
            failure(f"단일 이미지 표시 중 오류: {e}")
            # 오류 시 기본 표시
            ui.image(image).classes('max-w-full max-h-full object-contain')
    
    def display_image_grid(self, images):
        """다중 이미지 그리드 표시"""
        with ui.grid(columns=2).classes('w-full gap-2'):
            for image in images:
                ui.image(image).classes('w-full h-auto object-contain')
    
    def optimize_image_for_display(self, image: Image, max_size: int = 2048) -> Image:
        """이미지 표시용 최적화 (원본 크기 보존, UI에서만 비율 맞춤)"""
        try:
            process_emoji(f"이미지 최적화 시작: {image.size}")
            
            # 원본 크기 보존 (최적화하지 않고 그대로 반환)
            # UI에서 CSS로 비율을 맞추므로 이미지 자체는 원본 유지
            success(f"원본 크기 보존: {image.size}, RGB")
            return image.convert('RGB')
            
        except Exception as e:
            failure(f"이미지 최적화 중 오류: {e}")
            return image.convert('RGB')

class Img2ImgTab(BaseTab):
    """이미지→이미지 탭 - 개선안 5 적용"""
    
    def __init__(self, state_manager: StateManager, tab_manager):
        super().__init__(state_manager, tab_manager)
        self.tab_id = 'img2img'
        self.upload_area = None
        self.result_area = None
        self.original_image = None  # 원본 이미지 (영구 보존)
        self.generated_image = None  # 생성 결과 (독립 관리)
    
    def render(self, container):
        """I2I 탭 렌더링 - 좌우 분할 뷰 (반응형 높이)"""
        with container:
            # 좌우 분할: 원본 | 결과 (반응형 높이)
            with ui.splitter(value=45).classes('w-full h-full min-h-[500px]') as splitter:
                with splitter.before:
                    self.render_original_section()
                
                with splitter.after:
                    self.render_result_section()
            
            # 전달 버튼 영역
            self.transfer_area = ui.element('div').classes('w-full')
    
    def render_original_section(self):
        """원본 이미지 섹션 (반응형 높이)"""
        with ui.column().classes('w-full h-full p-3'):
            ui.label('원본 이미지').classes('text-sm font-medium mb-3 text-green-400')
            
            # 반응형 높이 영역
            self.upload_area = ui.element('div').classes(
                'w-full flex-1 border-2 border-dashed border-green-500 '
                'rounded-lg bg-gray-800 flex items-center justify-center cursor-pointer upload-area '
                'min-h-[400px]'
            ).props(f'data-tab-id={self.tab_id}')
            
            # 드래그 앤 드롭 + 클릭 업로드
            self.setup_upload_area()
    
    def render_result_section(self):
        """생성 결과 섹션 (반응형 높이)"""
        with ui.column().classes('w-full h-full p-3'):
            ui.label('생성 결과').classes('text-sm font-medium mb-3 text-blue-400')
            
            self.result_area = ui.element('div').classes(
                'w-full flex-1 border border-blue-500 rounded-lg bg-gray-800 '
                'flex items-center justify-center min-h-[400px]'
            )
            
            with self.result_area:
                ui.label('생성 버튼을 클릭하세요').classes('text-gray-400')
    
    def setup_upload_area(self):
        """업로드 영역 설정 - WebSocket 연결 중단 방지"""
        # UI 요소 존재 여부 및 클라이언트 상태 확인
        if not self.upload_area or not hasattr(self.upload_area, 'client') or not self.upload_area.client:
            warning_emoji(r"업로드 영역이 없거나 클라이언트가 없음 - 설정 건너뜀")
            return
            
        try:
            with self.upload_area:
                # 기본 업로드 UI
                with ui.column().classes('items-center'):
                    ui.icon('cloud_upload').classes('text-4xl text-green-400 mb-2')
                    ui.label('이미지를 드래그하거나 클릭하세요').classes('text-green-400')
                    ui.label('(최대 10MB, 권장: 2048x2048 이하)').classes('text-xs text-gray-500')
                    
                    # 숨겨진 파일 입력 - 크기 제한 및 압축 적용
                    ui.upload(
                        on_upload=self.handle_upload,
                        auto_upload=True,
                        multiple=False
                    ).props('accept=image/*').classes('mt-2')
            
            # 기존 원본 이미지 확인 (무한 재귀 방지)
            if not hasattr(self, '_initialized'):
                self.check_existing_original_image()
                self._initialized = True
            
            # JavaScript 드래그 앤 드롭 설정
            self.setup_drag_and_drop()
            
        except RuntimeError as e:
            if "client has been deleted" in str(e):
                warning_emoji(r"클라이언트가 삭제됨 - 업로드 영역 설정 건너뜀")
            else:
                failure(f"업로드 영역 설정 중 오류: {e}")
        except Exception as e:
            failure(f"업로드 영역 설정 중 오류: {e}")
    
    def check_existing_original_image(self):
        """기존 원본 이미지 확인 (무한 재귀 방지)"""
        try:
            original_image = self.state.get_init_image()
            if original_image and not hasattr(self, '_image_checked'):
                self.set_original_image(original_image)
                self._image_checked = True
        except Exception as e:
            warning_emoji(f"기존 이미지 확인 중 오류: {e}")
    
    def set_original_image(self, image: Image):
        """원본 이미지 설정 (영구 보존) - 이미지 프리뷰 강화"""
        try:
            process_emoji(f"원본 이미지 설정 시작: {image.size}")
            
            # 이미지 크기 및 형식 검증
            if not self.validate_image(image):
                failure(r"이미지 검증 실패")
                return
            
            # 원본 이미지 영구 보존
            self.original_image = image
            success(f"원본 이미지 메모리 보존: {image.size}")
            
            # StateManager에 영구 보존 (이미지 프리뷰 강화)
            process_emoji(r"StateManager에 원본 이미지 저장 시작")
            self.state.set_init_image(image)
            success(r"StateManager에 원본 이미지 보존 완료")
            
            # UI 요소 존재 여부 체크 및 강제 재생성
            if not self._check_ui_elements():
                warning_emoji(r"UI 요소가 삭제됨 - 강제 재생성 시작")
                self._force_recreate_ui()
                return
            
            # 업로드 영역 업데이트 (결과 영역은 절대 건드리지 않음)
            if self.upload_area:
                try:
                    process_emoji(r"원본 영역 업데이트 시작")
                    
                    # UI 업데이트 시도 (오류가 있어도 계속 진행)
                    try:
                        self.upload_area.clear()
                        success(r"업로드 영역 클리어 완료")
                    except RuntimeError as e:
                        if "client has been deleted" in str(e):
                            warning_emoji(r"클라이언트가 삭제됨 - 강제 재생성")
                            self._force_recreate_ui()
                            return
                        else:
                            warning_emoji(f"업로드 영역 클리어 실패: {e}")
                            return
                    except Exception as e:
                        warning_emoji(f"업로드 영역 클리어 중 예상치 못한 오류: {e}")
                        return
                    
                    # 이미지 표시 시도
                    try:
                        with self.upload_area:
                            # 원본 이미지 직접 표시 (최적화하지 않음)
                            process_emoji(f"원본 이미지 직접 표시: {image.size}")
                            
                            # 이미지 표시
                            buffer = io.BytesIO()
                            image.save(buffer, format='PNG', optimize=True)
                            img_str = base64.b64encode(buffer.getvalue()).decode()
                            
                            with ui.column().classes('w-full h-full items-center justify-center'):
                                ui.image(f'data:image/png;base64,{img_str}').classes(
                                    'max-w-full max-h-full object-contain rounded-lg shadow-lg'
                                ).style('width: auto; height: auto; max-width: 100%; max-height: 100%;')
                                
                                # 이미지 정보
                                with ui.row().classes('mt-2 text-sm text-gray-400'):
                                    ui.label(f'원본: {image.size[0]}×{image.size[1]}')
                        
                        success(r"원본 영역 업데이트 완료")
                    except Exception as e:
                        failure(f"이미지 표시 중 오류: {e}")
                        # 이미지 표시 실패 시 기본 메시지 표시
                        try:
                            with self.upload_area:
                                with ui.column().classes('w-full h-full items-center justify-center'):
                                    ui.label('이미지가 로드되었습니다').classes('text-green-400')
                                    ui.label(f'크기: {image.size[0]}×{image.size[1]}').classes('text-sm text-gray-400')
                        except:
                            pass
                
                except Exception as e:
                    failure(f"원본 영역 업데이트 중 오류: {e}")
                    # UI 오류가 있어도 StateManager에는 이미지가 저장되어 있음
            else:
                warning_emoji(r"업로드 영역이 없음")
                
        except Exception as e:
            failure(f"원본 이미지 설정 중 오류: {e}")
            import traceback
            traceback.print_exc()
    
    def validate_image(self, image: Image) -> bool:
        """이미지 유효성 검증"""
        try:
            # 크기 제한 (10MB = 약 10,000,000 픽셀)
            max_pixels = 10_000_000
            if image.size[0] * image.size[1] > max_pixels:
                warning_emoji(f"이미지가 너무 큽니다: {image.size[0]}×{image.size[1]} (최대: {max_pixels} 픽셀)")
                return False
            
            # 형식 검증
            if image.mode not in ['RGB', 'RGBA']:
                warning_emoji(f"지원하지 않는 이미지 형식: {image.mode}")
                return False
            
            return True
        except Exception as e:
            failure(f"이미지 검증 중 오류: {e}")
            return False
    
    def optimize_image_for_display(self, image: Image, max_size: int = 2048) -> Image:
        """이미지 표시용 최적화 (원본 크기 보존, UI에서만 비율 맞춤)"""
        try:
            process_emoji(f"이미지 최적화 시작: {image.size}")
            
            # 원본 크기 보존 (최적화하지 않고 그대로 반환)
            # UI에서 CSS로 비율을 맞추므로 이미지 자체는 원본 유지
            success(f"원본 크기 보존: {image.size}, RGB")
            return image.convert('RGB')
            
        except Exception as e:
            failure(f"이미지 최적화 중 오류: {e}")
            return image.convert('RGB')
    
    def _check_ui_elements(self) -> bool:
        """UI 요소 존재 여부 체크"""
        try:
            # 업로드 영역 체크
            if not self.upload_area:
                warning_emoji(r"업로드 영역이 없음")
                return False
            
            # 클라이언트 연결 상태 체크
            if not hasattr(self.upload_area, 'client') or not self.upload_area.client:
                warning_emoji(r"업로드 영역 클라이언트가 없음")
                return False
            
            # 결과 영역 체크
            if not self.result_area:
                warning_emoji(r"결과 영역이 없음")
                return False
            
            # 결과 영역 클라이언트 체크
            if not hasattr(self.result_area, 'client') or not self.result_area.client:
                warning_emoji(r"결과 영역 클라이언트가 없음")
                return False
            
            success(r"UI 요소 상태 정상")
            return True
            
        except Exception as e:
            failure(f"UI 요소 체크 중 오류: {e}")
            return False
    
    def _force_recreate_ui(self):
        """강제 UI 재생성 - 부모 요소 삭제 즉시 해결"""
        try:
            info(r"🚨 강제 UI 재생성 시작")
            
            # 현재 이미지 상태 보존
            current_image = self.original_image
            current_generated = self.generated_image
            
            info(f"📸 현재 상태 보존: 원본={current_image.size if current_image else None}, 생성={current_generated.size if current_generated else None}")
            
            # 탭 재활성화 (UI 재생성)
            process_emoji(r"탭 재활성화 시작")
            self.activate()
            
            # 이미지 상태 복원
            if current_image:
                process_emoji(f"원본 이미지 복원: {current_image.size}")
                self.original_image = current_image
                self.state.set_init_image(current_image)
                
                # UI 업데이트 시도
                try:
                    if self.upload_area and hasattr(self.upload_area, 'client') and self.upload_area.client:
                        self.upload_area.clear()
                        with self.upload_area:
                            # 이미지 최적화
                            optimized_image = self.optimize_image_for_display(current_image, max_size=2048)
                            
                            # 이미지 표시
                            buffer = io.BytesIO()
                            optimized_image.save(buffer, format='PNG', optimize=True)
                            img_str = base64.b64encode(buffer.getvalue()).decode()
                            
                            with ui.column().classes('w-full h-full items-center justify-center'):
                                ui.image(f'data:image/png;base64,{img_str}').classes(
                                    'max-w-full max-h-full object-contain rounded-lg shadow-lg'
                                ).style('width: auto; height: auto; max-width: 100%; max-height: 100%;')
                                
                                # 이미지 정보
                                with ui.row().classes('mt-2 text-sm text-gray-400'):
                                    ui.label(f'원본: {current_image.size[0]}×{current_image.size[1]}')
                        
                        success(r"원본 이미지 UI 복원 완료")
                except Exception as e:
                    warning_emoji(f"원본 이미지 UI 복원 실패: {e}")
            
            if current_generated:
                process_emoji(f"생성된 이미지 복원: {current_generated.size}")
                self.generated_image = current_generated
                
                # 결과 영역 업데이트 시도
                try:
                    if self.result_area and hasattr(self.result_area, 'client') and self.result_area.client:
                        self.result_area.clear()
                        with self.result_area:
                            # 이미지 최적화
                            optimized_image = self.optimize_image_for_display(current_generated, max_size=2048)
                            
                            # 이미지 표시
                            buffer = io.BytesIO()
                            optimized_image.save(buffer, format='PNG', optimize=True)
                            img_str = base64.b64encode(buffer.getvalue()).decode()
                            
                            with ui.column().classes('w-full h-full items-center justify-center'):
                                ui.image(f'data:image/png;base64,{img_str}').classes(
                                    'max-w-full max-h-full object-contain rounded-lg shadow-lg'
                                ).style('width: auto; height: auto; max-width: 100%; max-height: 100%;')
                                
                                # 이미지 정보
                                with ui.row().classes('mt-2 text-sm text-gray-400'):
                                    ui.label(f'생성됨: {current_generated.size[0]}×{current_generated.size[1]}')
                                
                                # 전달 버튼
                                ui.button(
                                    '다른 탭으로 전달',
                                    icon='send',
                                    on_click=lambda: self.create_transfer_buttons(current_generated)
                                ).props('outline size=sm')
                        
                        success(r"생성된 이미지 UI 복원 완료")
                except Exception as e:
                    warning_emoji(f"생성된 이미지 UI 복원 실패: {e}")
            
            success(r"강제 UI 재생성 완료")
            
        except Exception as e:
            failure(f"강제 UI 재생성 중 오류: {e}")
            import traceback
            traceback.print_exc()
    
    def _update_ui_only(self, image: Image):
        """UI 업데이트만 수행 (StateManager 저장 없음) - 부모 요소 삭제 방지"""
        try:
            process_emoji(f"UI 전용 업데이트 시작: {image.size}")
            
            # 업로드 영역 업데이트 (결과 영역은 절대 건드리지 않음)
            if self.upload_area:
                try:
                    process_emoji(r"원본 영역 UI 업데이트 시작")
                    
                    # UI 요소 존재 여부 및 클라이언트 상태 확인
                    if hasattr(self.upload_area, 'client') and self.upload_area.client:
                        try:
                            self.upload_area.clear()
                        except RuntimeError as e:
                            if "client has been deleted" in str(e):
                                warning_emoji(r"클라이언트가 삭제됨 - UI 업데이트 건너뜀")
                                return
                            else:
                                raise e
                    else:
                        warning_emoji(r"업로드 영역 클라이언트가 없음 - UI 업데이트 건너뜀")
                        return
                    
                    with self.upload_area:
                        # 이미지 최적화 (2048까지 허용)
                        optimized_image = self.optimize_image_for_display(image, max_size=2048)
                        
                        # 이미지 표시
                        buffer = io.BytesIO()
                        optimized_image.save(buffer, format='PNG', optimize=True)
                        img_str = base64.b64encode(buffer.getvalue()).decode()
                        
                        with ui.column().classes('w-full h-full items-center justify-center'):
                            ui.image(f'data:image/png;base64,{img_str}').classes(
                                'max-w-full max-h-full object-contain rounded-lg shadow-lg'
                            ).style('width: 100%; height: 100%;')
                    
                    success(r"원본 영역 UI 업데이트 완료")
                except Exception as e:
                    failure(f"원본 영역 UI 업데이트 실패: {e}")
                    # 오류 시 기본 메시지 표시
                    try:
                        if self.upload_area and hasattr(self.upload_area, 'client') and self.upload_area.client:
                            self.upload_area.clear()
                            with self.upload_area:
                                with ui.column().classes('w-full h-full items-center justify-center'):
                                    ui.label('이미지 표시 중 오류가 발생했습니다').classes('text-red-500')
                    except Exception as ui_error:
                        warning_emoji(f"기본 메시지 표시 실패: {ui_error}")
            else:
                warning_emoji(r"업로드 영역이 없음")
                
        except Exception as e:
            failure(f"UI 전용 업데이트 중 오류: {e}")
            import traceback
            traceback.print_exc()
    
    def set_generated_image(self, image: Image):
        """생성 결과 이미지 설정 (원본 이미지 보존 + 결과 영역만 업데이트)"""
        try:
            process_emoji(f"생성 결과 이미지 설정 시작: {image.size}")
            
            # 원본 이미지 보존 확인
            if self.original_image:
                success(f"원본 이미지 보존됨: {self.original_image.size}")
            else:
                warning_emoji(r"원본 이미지가 없음")
            
            self.generated_image = image
            
            # UI 요소 존재 여부 체크 및 강제 재생성
            if not self._check_ui_elements():
                warning_emoji(r"UI 요소가 삭제됨 - 강제 재생성 시작")
                self._force_recreate_ui()
                return
            
            # 결과 영역만 업데이트 (원본 영역은 절대 건드리지 않음)
            if self.result_area:
                process_emoji(r"결과 영역 업데이트 시작")
                
                # UI 요소 존재 여부 및 클라이언트 상태 확인
                if hasattr(self.result_area, 'client') and self.result_area.client:
                    try:
                        self.result_area.clear()
                    except RuntimeError as e:
                        if "client has been deleted" in str(e):
                            warning_emoji(r"클라이언트가 삭제됨 - 강제 재생성")
                            self._force_recreate_ui()
                            return
                        else:
                            raise e
                else:
                    warning_emoji(r"결과 영역 클라이언트가 없음 - 강제 재생성")
                    self._force_recreate_ui()
                    return
                
                with self.result_area:
                    # 원본 이미지 직접 표시 (최적화하지 않음)
                    process_emoji(f"생성된 이미지 직접 표시: {image.size}")
                    
                    # 이미지 표시
                    buffer = io.BytesIO()
                    image.save(buffer, format='PNG', optimize=True)
                    img_str = base64.b64encode(buffer.getvalue()).decode()
                    
                    with ui.column().classes('w-full h-full items-center justify-center'):
                        ui.image(f'data:image/png;base64,{img_str}').classes(
                            'max-w-full max-h-full object-contain rounded-lg shadow-lg'
                        ).style('width: auto; height: auto; max-width: 100%; max-height: 100%;')
                        
                        # 이미지 정보
                        with ui.row().classes('mt-2 text-sm text-gray-400'):
                            ui.label(f'생성됨: {image.size[0]}×{image.size[1]}')
                        
                        # 전달 버튼
                        ui.button(
                            '다른 탭으로 전달',
                            icon='send',
                            on_click=lambda: self.create_transfer_buttons(image)
                        ).props('outline size=sm')
                
                success(r"결과 영역 업데이트 완료")
                
                # 원본 이미지가 여전히 보존되는지 최종 확인
                if self.original_image:
                    success(f"원본 이미지 여전히 보존됨: {self.original_image.size}")
                else:
                    failure(r"원본 이미지가 사라짐!")
            else:
                warning_emoji(r"결과 영역이 없음")
                
        except Exception as e:
            failure(f"생성 결과 이미지 설정 중 오류: {e}")
            import traceback
            traceback.print_exc()
    
    def reset_upload(self):
        """업로드 초기화 (무한 재귀 방지)"""
        try:
            self.original_image = None
            if not hasattr(self, '_resetting'):
                self._resetting = True
                self.state.set_init_image(None)
                self._resetting = False
            
            # 상태 초기화
            self._image_checked = False
            self._initialized = False
            
            self.setup_upload_area()
        except Exception as e:
            failure(f"업로드 초기화 중 오류: {e}")
    
    def activate(self):
        """탭 활성화 (이벤트 구독 및 기존 이미지 복원) - 중복 구독 방지"""
        try:
            process_emoji(r"Img2Img 탭 활성화 시작")
            self.is_active = True
            self.state.set('current_mode', 'img2img')
            
            # 이벤트 구독 (중복 구독 방지 강화)
            if not hasattr(self, '_subscribed') or not self._subscribed:
                info(r"📡 이벤트 구독 시작")
                
                # 기존 구독 해제 (안전장치)
                try:
                    self.state.unsubscribe('generation_completed', self.on_generation_completed)
                except:
                    pass
                try:
                    self.state.unsubscribe('init_image_changed', self.on_init_image_changed)
                except:
                    pass
                try:
                    self.state.unsubscribe('generated_images_changed', self.on_generated_images_changed)
                except:
                    pass
                
                # 새로운 구독 등록
                self.state.subscribe('generation_completed', self.on_generation_completed)
                self.state.subscribe('init_image_changed', self.on_init_image_changed)
                self.state.subscribe('generated_images_changed', self.on_generated_images_changed)
                
                self._subscribed = True
                success(r"이벤트 구독 완료")
            else:
                info_emoji(r"이미 구독됨 - 중복 구독 방지")
            
            # 기존 이미지 상태 복원 (UI 동기화 강화)
            self.restore_image_state()
            
        except Exception as e:
            failure(f"탭 활성화 중 오류: {e}")
            import traceback
            traceback.print_exc()
    
    def cleanup(self):
        """탭 정리 (안전한 이벤트 구독 해제)"""
        try:
            process_emoji(r"Img2Img 탭 정리 시작")
            self.is_active = False
            
            # 안전한 이벤트 구독 해제
            if hasattr(self, '_subscribed') and self._subscribed:
                info(r"📡 이벤트 구독 해제 시작")
                try:
                    self.state.unsubscribe('generation_completed', self.on_generation_completed)
                    success(r"generation_completed 구독 해제 완료")
                except Exception as e:
                    warning_emoji(f"generation_completed 구독 해제 실패: {e}")
                
                try:
                    self.state.unsubscribe('init_image_changed', self.on_init_image_changed)
                    success(r"init_image_changed 구독 해제 완료")
                except Exception as e:
                    warning_emoji(f"init_image_changed 구독 해제 실패: {e}")
                
                try:
                    self.state.unsubscribe('generated_images_changed', self.on_generated_images_changed)
                    success(r"generated_images_changed 구독 해제 완료")
                except Exception as e:
                    warning_emoji(f"generated_images_changed 구독 해제 실패: {e}")
                
                self._subscribed = False
                success(r"이벤트 구독 해제 완료")
            
        except Exception as e:
            failure(f"탭 정리 중 오류: {e}")
            import traceback
            traceback.print_exc()
    
    def restore_image_state(self):
        """기존 이미지 상태 복원 (UI 동기화 강화)"""
        try:
            process_emoji(r"이미지 상태 복원 시작")
            
            # 원본 이미지 복원
            init_image = self.state.get_init_image()
            if init_image:
                success(f"원본 이미지 복원: {init_image.size}")
                self.set_original_image(init_image)
            else:
                info_emoji(r"원본 이미지 없음")
            
            # 생성된 이미지 복원
            generated_images = self.state.get_generated_images()
            if generated_images:
                success(f"생성된 이미지 복원: {len(generated_images)}개")
                self.set_generated_image(generated_images[0])
            else:
                info_emoji(r"생성된 이미지 없음")
                
        except Exception as e:
            failure(f"이미지 상태 복원 중 오류: {e}")
            import traceback
            traceback.print_exc()
    
    def on_generation_completed(self, event_data):
        """생성 완료 이벤트 처리 (원본 이미지 보존 + 결과 이미지 추가) - 원본 이미지 건드리지 않음"""
        debug_emoji(r"Img2Img: generation_completed 이벤트 수신")
        info(f"   - 이벤트 데이터: {event_data}")
        info(f"   - 탭 활성 상태: {self.is_active}")
        
        if not self.is_active:
            warning_emoji(r"탭이 비활성 상태 - 이벤트 무시")
            return
        
        if hasattr(self, '_processing_generation') and self._processing_generation:
            warning_emoji(r"이미 처리 중 - 중복 이벤트 무시")
            return
        
        try:
            self._processing_generation = True
            images = event_data.get('images', [])
            info(f"   - 수신된 이미지 개수: {len(images)}")
            
            if images:
                success(r"생성된 이미지 표시 시작")
                
                # 원본 이미지 보존 확인 (건드리지 않음)
                if self.original_image:
                    success(f"원본 이미지 보존 확인: {self.original_image.size}")
                else:
                    warning_emoji(r"원본 이미지가 없음")
                
                # 결과 영역에만 생성된 이미지 추가 (원본 영역은 절대 건드리지 않음)
                generated_image = images[0]
                success(f"결과 영역에 이미지 추가: {generated_image.size}")
                self.set_generated_image(generated_image)
                
                # 최종 상태 확인
                if self.original_image:
                    success(f"원본 이미지 여전히 표시됨: {self.original_image.size}")
                if self.generated_image:
                    success(f"생성된 이미지 표시됨: {self.generated_image.size}")
                
                success(r"생성된 이미지 표시 완료 (원본 + 결과 동시 표시)")
            else:
                warning_emoji(r"생성된 이미지가 없음")
                
        except Exception as e:
            failure(f"생성 완료 이벤트 처리 중 오류: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._processing_generation = False
    
    def on_init_image_changed(self, event_data):
        """원본 이미지 변경 이벤트 처리 (중복 호출 방지 강화)"""
        debug_emoji(r"Img2Img: init_image_changed 이벤트 수신")
        info(f"   - 이벤트 데이터: {event_data}")
        info(f"   - 탭 활성 상태: {self.is_active}")
        
        if not self.is_active:
            warning_emoji(r"탭이 비활성 상태 - 이벤트 무시")
            return
        
        # 중복 호출 방지 (업로드 중에는 이벤트 무시)
        if hasattr(self, '_processing_init_change') and self._processing_init_change:
            warning_emoji(r"이미 처리 중 - 중복 이벤트 무시")
            return
        
        # 업로드 중 중복 호출 방지
        if hasattr(self, '_uploading') and self._uploading:
            warning_emoji(r"업로드 중 - 이벤트 무시")
            return
        
        try:
            self._processing_init_change = True
            status = event_data.get('status')
            info(f"   - 상태: {status}")
            
            if status == 'success':
                success(r"원본 이미지 업데이트 시작")
                original_image = self.state.get_init_image()
                if original_image:
                    # UI 업데이트만 수행 (StateManager 저장은 건너뛰기)
                    self._update_ui_only(original_image)
                    success(r"원본 이미지 UI 업데이트 완료")
                else:
                    warning_emoji(r"StateManager에서 원본 이미지를 찾을 수 없음")
            else:
                info_emoji(f"원본 이미지 상태: {status}")
                
        except Exception as e:
            failure(f"원본 이미지 변경 이벤트 처리 중 오류: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._processing_init_change = False
    
    def on_generated_images_changed(self, event_data):
        """생성된 이미지 변경 이벤트 처리 (디버깅 강화)"""
        debug_emoji(r"Img2Img: generated_images_changed 이벤트 수신")
        info(f"   - 이벤트 데이터: {event_data}")
        info(f"   - 탭 활성 상태: {self.is_active}")
        
        if not self.is_active:
            warning_emoji(r"탭이 비활성 상태 - 이벤트 무시")
            return
        
        if hasattr(self, '_processing_generated_change') and self._processing_generated_change:
            warning_emoji(r"이미 처리 중 - 중복 이벤트 무시")
            return
        
        try:
            self._processing_generated_change = True
            count = event_data.get('count', 0)
            info(f"   - 이미지 개수: {count}")
            
            if count > 0:
                success(r"생성된 이미지 업데이트 시작")
                generated_images = self.state.get_generated_images()
                if generated_images:
                    self.set_generated_image(generated_images[0])
                    success(r"생성된 이미지 업데이트 완료")
                else:
                    warning_emoji(r"StateManager에서 생성된 이미지를 찾을 수 없음")
            else:
                info_emoji(r"생성된 이미지 없음")
                
        except Exception as e:
            failure(f"생성된 이미지 변경 이벤트 처리 중 오류: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._processing_generated_change = False

    def setup_drag_and_drop(self):
        """드래그 앤 드롭 JavaScript 설정"""
        ui.run_javascript(f"""
        // 드래그 앤 드롭 설정
        const uploadArea = document.querySelector('[data-tab-id="{self.tab_id}"] .upload-area');
        
        if (uploadArea) {{
            uploadArea.addEventListener('dragover', function(e) {{
                e.preventDefault();
                this.style.borderColor = '#10b981';
                this.style.backgroundColor = '#065f46';
            }});
            
            uploadArea.addEventListener('dragleave', function(e) {{
                e.preventDefault();
                this.style.borderColor = '#6b7280';
                this.style.backgroundColor = '#1f2937';
            }});
            
            uploadArea.addEventListener('drop', function(e) {{
                e.preventDefault();
                this.style.borderColor = '#6b7280';
                this.style.backgroundColor = '#1f2937';
                
                const files = e.dataTransfer.files;
                if (files.length > 0) {{
                    const file = files[0];
                    if (file.type.startsWith('image/')) {{
                        // 파일을 Python으로 전송
                        const reader = new FileReader();
                        reader.onload = function(e) {{
                            window.pyCallback_{self.tab_id}_upload({{
                                'content': e.target.result,
                                'name': file.name,
                                'type': file.type
                            }});
                        }};
                        reader.readAsDataURL(file);
                    }}
                }}
            }});
        }}
        """)
        
        # Python 콜백 등록
        self.js_bridge.register_callback('upload', self.handle_js_upload)
    
    def handle_upload(self, upload_event):
        """업로드 이미지 처리 (리사이즈 금지)"""
        try:
            # PIL 이미지 변환만
            image = Image.open(io.BytesIO(upload_event.content))
            
            # 상태 저장 (원본 그대로)
            self.state.set('init_image', image)
            
            # 프리뷰 표시 (CSS 반응형)
            self.update_preview_display(image)
            
        except Exception as e:
            failure(f"업로드 실패: {e}")
            self.safe_notify(f'업로드 실패: {str(e)}', 'negative')
    
    def optimize_image_for_upload(self, image: Image, max_size: int = 2048) -> Image:
        """업로드용 이미지 최적화 (원본 크기 보존)"""
        try:
            original_size = image.size
            process_emoji(f"이미지 최적화 시작: {original_size}")
            
            # 원본 크기 보존 (리사이즈하지 않음)
            # RGB 변환만 수행
            if image.mode != 'RGB':
                image = image.convert('RGB')
                canvas_emoji(r"모드 변환: {image.mode}")
            
            success(f"원본 크기 보존: {image.size}, {image.mode}")
            return image
            
        except Exception as e:
            failure(f"이미지 최적화 중 오류: {e}")
            return image
    
    def handle_js_upload(self, data):
        """JavaScript 드래그 앤 드롭 처리 - 이미지 프리뷰 강화"""
        try:
            debug_emoji(f"JS 업로드 시작: 데이터 타입={type(data)}")
            
            # Base64 데이터 디코딩
            header, encoded = data['content'].split(',', 1)
            image_data = base64.b64decode(encoded)
            
            info(f"📁 JS 업로드 크기: {len(image_data)} 바이트")
            
            # 크기 제한 (10MB)
            if len(image_data) > 10 * 1024 * 1024:
                ui.notify('파일이 너무 큽니다 (최대 10MB)', type='negative')
                return
            
            # 이미지 로드 및 검증
            image = Image.open(io.BytesIO(image_data))
            image_emoji(f"JS 이미지 로드됨: {image.size}, {image.mode}")
            
            # 이미지 유효성 검증
            if not self.validate_image(image):
                ui.notify('지원하지 않는 이미지 형식입니다', type='negative')
                return
            
            # 이미지 압축 (WebSocket 연결 중단 방지)
            optimized_image = self.optimize_image_for_upload(image)
            process_emoji(f"JS 이미지 최적화 완료: {optimized_image.size}")
            
            # 원본 이미지 설정 (업로드 중 플래그 설정)
            process_emoji(f"JS 원본 이미지 설정 시작: {optimized_image.size}")
            self._uploading = True
            try:
                self.set_original_image(optimized_image)
            finally:
                self._uploading = False
            
            # 성공 알림 (UI 컨텍스트 안전하게)
            self.safe_notify('이미지 업로드 완료', 'positive')
            
            success(f"JS 업로드 완료: {optimized_image.size}")
                
        except Exception as e:
            failure(f"JS 업로드 실패: {e}")
            import traceback
            traceback.print_exc()
            self.safe_notify(f'업로드 실패: {str(e)}', 'negative')

class InpaintTab(BaseTab):
    """인페인팅 탭"""
    
    def __init__(self, state_manager: StateManager, tab_manager):
        super().__init__(state_manager, tab_manager)
        self.tab_id = 'inpaint'
    
    def render(self, container):
        """인페인팅 탭 렌더링"""
        with container:
            with ui.card().classes('w-full h-96 flex items-center justify-center bg-gray-800'):
                ui.label('인페인팅 기능은 곧 구현됩니다').classes('text-gray-400 text-center')
    
    def activate(self):
        """탭 활성화"""
        self.is_active = True
        self.state.set('current_mode', 'inpaint')
    
    def cleanup(self):
        """탭 정리"""
        self.is_active = False

class UpscaleTab(BaseTab):
    """업스케일 탭 - Fabric.js Canvas 통합"""
    
    def __init__(self, state_manager: StateManager, tab_manager):
        super().__init__(state_manager, tab_manager)
        self.tab_id = 'upscale'
        
        # Fabric.js Canvas 설정
        self.setup_canvas(f'{self.tab_id}-canvas')
        
        # 업스케일 설정
        self.upscale_factor = 2.0
        self.upscale_method = 'lanczos'
    
    def render(self, container):
        """업스케일 탭 렌더링 - Fabric.js Canvas 사용"""
        self.container = container
        
        with container:
            # 상단 컨트롤 패널
            with ui.card().classes('w-full mb-4 p-4 bg-gray-800'):
                with ui.row().classes('w-full items-center gap-4'):
                    ui.label('업스케일 배율:').classes('text-white')
                    self.scale_slider = ui.slider(min=1.0, max=4.0, step=0.5, value=2.0).classes('flex-1')
                    ui.label('2.0x').classes('text-white min-w-[40px]')
                    
                    ui.label('방법:').classes('text-white')
                    self.method_select = ui.select(
                        options=['lanczos', 'nearest', 'bilinear'],
                        value='lanczos'
                    ).classes('min-w-[120px]')
                    
                    ui.button('업스케일', on_click=self.upscale_image).classes('bg-blue-600 text-white')
            
            # Fabric.js Canvas 컨테이너
            with ui.card().classes('w-full h-full min-h-[500px] bg-gray-800'):
                # Canvas 요소
                ui.element('canvas').classes('w-full h-full').props(f'id="{self.canvas_id}"')
                
                # 플레이스홀더 (Canvas 로드 전)
                with ui.element('div').classes('absolute inset-0 flex items-center justify-center bg-gray-800').props(f'id="{self.canvas_id}-placeholder"'):
                    with ui.column().classes('items-center justify-center'):
                        ui.icon('zoom_in', size='4em').classes('text-gray-500 mb-4')
                        ui.label('업로드된 이미지를 업스케일하세요').classes(
                            'text-gray-400 text-center text-lg mb-2'
                        )
                        ui.label('이미지를 드래그하여 업로드하거나 다른 탭에서 전달하세요').classes(
                            'text-gray-500 text-center text-sm'
                        )
                
                # Canvas 초기화 스크립트
                ui.add_head_html(f'''
                    <script>
                        function initCanvas_{self.canvas_id}() {{
                            if (typeof fabric !== 'undefined') {{
                                if (typeof createCanvasManager === 'function') {{
                                    createCanvasManager('{self.canvas_id}');
                                    console.log('✅ {self.tab_id} Canvas 매니저 생성됨');
                                    
                                    const placeholder = document.getElementById('{self.canvas_id}-placeholder');
                                    if (placeholder) {{
                                        placeholder.style.display = 'none';
                                    }}
                                }}
                            }} else {{
                                setTimeout(initCanvas_{self.canvas_id}, 100);
                            }}
                        }}
                        
                        if (document.readyState === 'loading') {{
                            document.addEventListener('DOMContentLoaded', initCanvas_{self.canvas_id});
                        }} else {{
                            initCanvas_{self.canvas_id}();
                        }}
                    </script>
                ''')
    
    def activate(self):
        """탭 활성화"""
        self.is_active = True
        self.state.set('current_mode', 'upscale')
        success(f"{self.tab_id} 탭 활성화")
        
        # 이벤트 구독
        self.state.subscribe('generated_images_changed', self.on_images_changed)
    
    def cleanup(self):
        """탭 정리"""
        self.is_active = False
        self.state.unsubscribe('generated_images_changed', self.on_images_changed)
        info(f"🧹 {self.tab_id} 탭 정리")
    
    def on_images_changed(self, event_data):
        """이미지 변경 이벤트 처리"""
        if not self.is_active:
            return
        
        images = event_data.get('images', [])
        if images:
            self.display_image(images[0])
    
    def display_image(self, image: Image.Image):
        """이미지 표시"""
        if self.canvas_bridge:
            if self.canvas_bridge.wait_for_ready(timeout=5.0):
                success = self.load_image_to_canvas(image)
                if success:
                    success(f"{self.tab_id} 이미지 로드 성공")
                else:
                    failure(f"{self.tab_id} 이미지 로드 실패")
            else:
                warning_emoji(f"{self.tab_id} Canvas 준비 시간 초과")
    
    def upscale_image(self):
        """이미지 업스케일"""
        if not self.canvas_bridge or not self.canvas_bridge.is_ready:
            warning_emoji(r"Canvas가 준비되지 않음")
            return
        
        try:
            scale_factor = self.scale_slider.value
            method = self.method_select.value
            
            process_emoji(f"이미지 업스케일 시작: {scale_factor}x, 방법: {method}")
            
            # JavaScript에서 업스케일 실행
            script = f"""
                const manager = getCanvasManager('{self.canvas_id}');
                if (manager) {{
                    const objects = manager.objects;
                    for (const [id, obj] of objects) {{
                        if (obj.type === 'image') {{
                            obj.scale({scale_factor});
                            manager.canvas.renderAll();
                            console.log('✅ 이미지 업스케일 완료');
                        }}
                    }}
                }}
            """
            ui.run_javascript(script)
            
        except Exception as e:
            failure(f"업스케일 실패: {e}")
    
    def optimize_image_for_display(self, image: Image.Image, max_size: int = 2048) -> Image.Image:
        """이미지 표시 최적화"""
        width, height = image.size
        
        if width > max_size or height > max_size:
            if width > height:
                new_width = max_size
                new_height = int(height * (max_size / width))
            else:
                new_height = max_size
                new_width = int(width * (max_size / height))
            
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        return image

class TabManager:
    """Image Pad 탭 시스템 관리"""
    
    def __init__(self, state_manager: StateManager):
        self.state = state_manager
        self.active_tab = None
        self.tabs = {}
        self.tab_history = []
        self.canvas_instances = {}
        
        # 기본 탭 등록
        self.register_default_tabs()
    
    def register_tab(self, tab_id: str, tab_class: Type[BaseTab]):
        """새로운 탭 등록"""
        self.tabs[tab_id] = tab_class(self.state, self)
        success(f"탭 등록: {tab_id}")
    
    def register_default_tabs(self):
        """기본 탭들 등록"""
        self.register_tab('txt2img', Txt2ImgTab)
        self.register_tab('img2img', Img2ImgTab)
        self.register_tab('inpaint', InpaintTab)
        self.register_tab('upscale', UpscaleTab)
    
    def switch_tab(self, tab_id: str):
        """탭 전환"""
        if tab_id not in self.tabs:
            failure(f"존재하지 않는 탭: {tab_id}")
            return False
        
        # 이전 탭 정리
        if self.active_tab:
            self.active_tab.cleanup()
        
        # 새 탭 활성화
        self.active_tab = self.tabs[tab_id]
        self.active_tab.activate()
        
        # 상태 업데이트
        self.state.set('current_tab', tab_id)
        self.tab_history.append(tab_id)
        
        # 불필요한 로그 제거 - 사용자가 실제로 탭을 클릭할 때만 로그 출력
        # process_emoji(f"탭 전환: {tab_id}")
        return True
    
    def get_transfer_targets(self, current_tab: str) -> List[str]:
        """현재 탭에서 전달 가능한 대상 탭들"""
        if current_tab == 'txt2img':
            return ['img2img', 'inpaint', 'upscale']
        elif current_tab in ['img2img', 'inpaint', 'upscale']:
            # 모든 이미지 기반 탭들은 서로 자유롭게 전환 가능 (T2I 제외)
            return [tab for tab in self.tabs.keys() if tab != 'txt2img']
        return []
    
    def transfer_image(self, image: Image, target_tab: str):
        """이미지와 함께 탭 전환"""
        if target_tab not in self.get_transfer_targets(self.state.get('current_tab')):
            return False
        
        # 이미지 전달
        self.state.set('current_image', image)
        
        # 탭 전환
        return self.switch_tab(target_tab)

class ImagePadTabSystem:
    """Image Pad 탭 시스템 메인 컴포넌트"""
    
    def __init__(self, state_manager: StateManager):
        self.state = state_manager
        self.tab_manager = TabManager(state_manager)
        self.current_tab_container = None
        
        # 이벤트 구독
        self.state.subscribe('mode_changed', self.on_mode_changed)
    
    def render(self):
        """Image Pad 탭 시스템 렌더링"""
        with ui.column().classes('w-full h-full'):
            # 탭 헤더
            self.render_tab_header()
            
            # 탭 컨텐츠
            self.current_tab_container = ui.element('div').classes('w-full flex-1')
            
            # 초기 탭 로드
            self.tab_manager.switch_tab('txt2img')
    
    def render_tab_header(self):
        """탭 헤더 렌더링"""
        with ui.card().classes('w-full p-2 mb-2 bg-gray-900'):
            with ui.row().classes('w-full gap-1'):
                # 기본 탭들
                self.create_tab_button('txt2img', 'T2I', 'text_fields', 'blue')
                self.create_tab_button('img2img', 'I2I', 'image', 'green')
                self.create_tab_button('inpaint', 'Inpaint', 'brush', 'purple')
                self.create_tab_button('upscale', 'Upscale', 'zoom_in', 'orange')
                
                # 더 많은 탭 추가 버튼
                ui.button(
                    icon='add',
                    on_click=self.show_more_tabs_dialog
                ).props('round flat').classes('ml-auto')
    
    def create_tab_button(self, tab_id: str, label: str, icon: str, color: str):
        """탭 버튼 생성"""
        current_tab = self.state.get('current_tab', 'txt2img')
        is_active = tab_id == current_tab
        
        # 전달 가능 여부 확인
        can_access = tab_id in self.tab_manager.get_transfer_targets(current_tab) or tab_id == current_tab
        
        button_props = f'{"unelevated" if is_active else "outline"} color={color} size=sm'
        if not can_access:
            button_props += ' disable'
        
        with ui.button(
            text=label,
            icon=icon,
            on_click=lambda: self.switch_tab(tab_id) if can_access else None
        ).props(button_props).classes('min-w-0'):
            if not can_access:
                ui.tooltip('현재 탭에서 접근할 수 없습니다')
    
    def switch_tab(self, tab_id: str):
        """탭 전환"""
        success = self.tab_manager.switch_tab(tab_id)
        
        if success and self.current_tab_container:
            # 탭 컨텐츠 업데이트
            self.current_tab_container.clear()
            with self.current_tab_container:
                self.tab_manager.active_tab.render(self.current_tab_container)
    
    def show_more_tabs_dialog(self):
        """더 많은 탭 추가 다이얼로그"""
        with ui.dialog() as dialog:
            with ui.card():
                ui.label('추가 탭').classes('text-lg font-bold mb-4')
                ui.label('추가 탭 기능은 곧 구현됩니다').classes('text-gray-600')
                ui.button('확인', on_click=dialog.close)
        dialog.open()
    
    def on_mode_changed(self, data: dict):
        """모드 변경 이벤트 처리"""
        mode = data.get('mode', 'txt2img')
        
        # 모드에 해당하는 탭으로 전환
        if mode in self.tab_manager.tabs:
            self.switch_tab(mode) 