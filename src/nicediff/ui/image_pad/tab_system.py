"""
Image Pad 탭 시스템 구현
개선안4에 따른 확장 가능한 탭 기반 시스템
"""

from nicegui import ui
from abc import ABC, abstractmethod
from typing import Type, List, Dict, Any, Callable
import asyncio
import json
import io
import base64
from PIL import Image
import numpy as np
from ...core.state_manager import StateManager

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
    """모든 탭의 기본 클래스"""
    
    def __init__(self, state_manager: StateManager, tab_manager):
        self.state = state_manager
        self.tab_manager = tab_manager
        self.tab_id = None
        self.container = None
        self.canvas = None
        self.is_active = False
        
        # JavaScript 통신 설정
        self.js_bridge = JSBridge(self.tab_id)
    
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
            ui.notify(f'{self.get_tab_info(target_tab)["name"]}으로 전달됨', type='positive')
        else:
            ui.notify('전달할 수 없습니다', type='warning')
    
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
    
    def render(self, container):
        """T2I 탭 렌더링"""
        with container:
            # 생성 결과 표시 영역
            with ui.card().classes('w-full h-96 flex items-center justify-center bg-gray-800'):
                self.result_display = ui.element('div').classes('w-full h-full')
                
                with self.result_display:
                    ui.label('생성 버튼을 클릭하여 이미지를 만드세요').classes(
                        'text-gray-400 text-center'
                    )
            
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
        """결과 이미지 표시"""
        if not self.result_display:
            return
            
        self.result_display.clear()
        
        with self.result_display:
            if len(images) == 1:
                # 단일 이미지 표시
                self.display_single_image(images[0])
            else:
                # 다중 이미지 그리드
                self.display_image_grid(images)
        
        # 전달 버튼 생성
        if self.transfer_area:
            self.transfer_area.clear()
            with self.transfer_area:
                self.create_transfer_buttons(images[0])
    
    def display_single_image(self, image):
        """단일 이미지 표시"""
        ui.image(image).classes('max-w-full max-h-full object-contain')
    
    def display_image_grid(self, images):
        """다중 이미지 그리드 표시"""
        with ui.grid(columns=2).classes('w-full gap-2'):
            for image in images:
                ui.image(image).classes('w-full h-auto object-contain')

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
        """I2I 탭 렌더링 - 좌우 분할 뷰"""
        with container:
            # 좌우 분할: 원본 | 결과
            with ui.splitter(value=50).classes('w-full h-96') as splitter:
                with splitter.before:
                    self.render_original_section()
                
                with splitter.after:
                    self.render_result_section()
            
            # 전달 버튼 영역
            self.transfer_area = ui.element('div').classes('w-full')
    
    def render_original_section(self):
        """원본 이미지 섹션"""
        with ui.column().classes('w-full h-full p-2'):
            ui.label('원본 이미지').classes('text-sm font-medium mb-2 text-green-400')
            
            # Props 메서드 오류 수정
            self.upload_area = ui.element('div').classes(
                'w-full flex-1 border-2 border-dashed border-green-500 '
                'rounded-lg bg-gray-800 flex items-center justify-center cursor-pointer upload-area'
            ).props(f'data-tab-id={self.tab_id}')
            
            # 드래그 앤 드롭 + 클릭 업로드
            self.setup_upload_area()
    
    def render_result_section(self):
        """생성 결과 섹션"""
        with ui.column().classes('w-full h-full p-2'):
            ui.label('생성 결과').classes('text-sm font-medium mb-2 text-blue-400')
            
            self.result_area = ui.element('div').classes(
                'w-full flex-1 border border-blue-500 rounded-lg bg-gray-800 '
                'flex items-center justify-center'
            )
            
            with self.result_area:
                ui.label('생성 버튼을 클릭하세요').classes('text-gray-400')
    
    def setup_upload_area(self):
        """업로드 영역 설정 - WebSocket 연결 중단 방지"""
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
    
    def check_existing_original_image(self):
        """기존 원본 이미지 확인 (무한 재귀 방지)"""
        try:
            original_image = self.state.get_init_image()
            if original_image and not hasattr(self, '_image_checked'):
                self.set_original_image(original_image)
                self._image_checked = True
        except Exception as e:
            print(f"⚠️ 기존 이미지 확인 중 오류: {e}")
    
    def set_original_image(self, image: Image):
        """원본 이미지 설정 (영구 보존) - WebSocket 연결 중단 방지"""
        try:
            # 이미지 크기 및 형식 검증
            if not self.validate_image(image):
                return
            
            self.original_image = image
            
            # StateManager에 영구 보존 (무한 재귀 방지)
            if not hasattr(self, '_setting_image'):
                self._setting_image = True
                self.state.set_init_image(image)
                self._setting_image = False
            
            # 업로드 영역 업데이트
            if self.upload_area:
                self.upload_area.clear()
                
                with self.upload_area:
                    # 이미지 압축 및 최적화
                    optimized_image = self.optimize_image_for_display(image)
                    
                    # 이미지 표시
                    buffer = io.BytesIO()
                    optimized_image.save(buffer, format='PNG', optimize=True)
                    img_str = base64.b64encode(buffer.getvalue()).decode()
                    
                    with ui.column().classes('w-full h-full items-center justify-center'):
                        ui.image(f'data:image/png;base64,{img_str}').classes(
                            'max-w-full max-h-full object-contain'
                        )
                        
                        # 이미지 정보
                        with ui.row().classes('mt-2 text-sm text-gray-400'):
                            ui.label(f'{image.size[0]}×{image.size[1]}')
                            ui.label(image.mode)
                        
                        # 새 이미지 버튼
                        ui.button(
                            '다른 이미지 선택',
                            icon='refresh',
                            on_click=self.reset_upload
                        ).props('outline size=sm')
        except Exception as e:
            print(f"❌ 원본 이미지 설정 중 오류: {e}")
    
    def validate_image(self, image: Image) -> bool:
        """이미지 유효성 검증"""
        try:
            # 크기 제한 (10MB = 약 10,000,000 픽셀)
            max_pixels = 10_000_000
            if image.size[0] * image.size[1] > max_pixels:
                print(f"⚠️ 이미지가 너무 큽니다: {image.size[0]}×{image.size[1]} (최대: {max_pixels} 픽셀)")
                return False
            
            # 형식 검증
            if image.mode not in ['RGB', 'RGBA']:
                print(f"⚠️ 지원하지 않는 이미지 형식: {image.mode}")
                return False
            
            return True
        except Exception as e:
            print(f"❌ 이미지 검증 중 오류: {e}")
            return False
    
    def optimize_image_for_display(self, image: Image, max_size: int = 512) -> Image:
        """이미지 최적화 (WebSocket 연결 중단 방지)"""
        try:
            # 크기가 큰 경우 리사이즈
            if max(image.size) > max_size:
                ratio = max_size / max(image.size)
                new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
                image = image.resize(new_size, Image.Resampling.LANCZOS)
            
            # RGB 변환
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            return image
        except Exception as e:
            print(f"❌ 이미지 최적화 중 오류: {e}")
            return image
    
    def set_generated_image(self, image: Image):
        """생성 결과 이미지 설정 (독립 관리) - WebSocket 연결 중단 방지"""
        try:
            self.generated_image = image
            
            # 결과 영역 업데이트
            if self.result_area:
                self.result_area.clear()
                
                with self.result_area:
                    # 이미지 최적화
                    optimized_image = self.optimize_image_for_display(image)
                    
                    # 이미지 표시
                    buffer = io.BytesIO()
                    optimized_image.save(buffer, format='PNG', optimize=True)
                    img_str = base64.b64encode(buffer.getvalue()).decode()
                    
                    with ui.column().classes('w-full h-full items-center justify-center'):
                        ui.image(f'data:image/png;base64,{img_str}').classes(
                            'max-w-full max-h-full object-contain'
                        )
                        
                        # 이미지 정보
                        with ui.row().classes('mt-2 text-sm text-gray-400'):
                            ui.label(f'생성됨: {image.size[0]}×{image.size[1]}')
                        
                        # 전달 버튼
                        ui.button(
                            '다른 탭으로 전달',
                            icon='send',
                            on_click=lambda: self.create_transfer_buttons(image)
                        ).props('outline size=sm')
        except Exception as e:
            print(f"❌ 생성 결과 이미지 설정 중 오류: {e}")
    
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
            print(f"❌ 업로드 초기화 중 오류: {e}")
    
    def activate(self):
        """탭 활성화 (이벤트 구독 및 기존 이미지 복원)"""
        try:
            print(f"🔄 Img2Img 탭 활성화 시작")
            self.is_active = True
            self.state.set('current_mode', 'img2img')
            
            # 이벤트 구독 (중복 구독 방지)
            if not hasattr(self, '_subscribed'):
                print(f"📡 이벤트 구독 시작")
                self.state.subscribe('generation_completed', self.on_generation_completed)
                self.state.subscribe('init_image_changed', self.on_init_image_changed)
                self.state.subscribe('generated_images_changed', self.on_generated_images_changed)
                self._subscribed = True
                print(f"✅ 이벤트 구독 완료")
            
            # 기존 이미지 상태 복원
            self.restore_image_state()
            
        except Exception as e:
            print(f"❌ 탭 활성화 중 오류: {e}")
    
    def cleanup(self):
        """탭 정리 (안전한 이벤트 구독 해제)"""
        try:
            print(f"🔄 Img2Img 탭 정리 시작")
            self.is_active = False
            
            # 안전한 이벤트 구독 해제
            if hasattr(self, '_subscribed') and self._subscribed:
                print(f"📡 이벤트 구독 해제 시작")
                try:
                    self.state.unsubscribe('generation_completed', self.on_generation_completed)
                except Exception as e:
                    print(f"⚠️ generation_completed 구독 해제 실패: {e}")
                
                try:
                    self.state.unsubscribe('init_image_changed', self.on_init_image_changed)
                except Exception as e:
                    print(f"⚠️ init_image_changed 구독 해제 실패: {e}")
                
                try:
                    self.state.unsubscribe('generated_images_changed', self.on_generated_images_changed)
                except Exception as e:
                    print(f"⚠️ generated_images_changed 구독 해제 실패: {e}")
                
                self._subscribed = False
                print(f"✅ 이벤트 구독 해제 완료")
            
        except Exception as e:
            print(f"❌ 탭 정리 중 오류: {e}")
    
    def restore_image_state(self):
        """기존 이미지 상태 복원"""
        try:
            print(f"🔄 이미지 상태 복원 시작")
            
            # 원본 이미지 복원
            init_image = self.state.get_init_image()
            if init_image:
                print(f"✅ 원본 이미지 복원: {init_image.size}")
                self.set_original_image(init_image)
            else:
                print(f"ℹ️ 원본 이미지 없음")
            
            # 생성된 이미지 복원
            generated_images = self.state.get_generated_images()
            if generated_images:
                print(f"✅ 생성된 이미지 복원: {len(generated_images)}개")
                self.set_generated_image(generated_images[0])
            else:
                print(f"ℹ️ 생성된 이미지 없음")
                
        except Exception as e:
            print(f"❌ 이미지 상태 복원 중 오류: {e}")
    
    def on_generation_completed(self, event_data):
        """생성 완료 이벤트 처리 (디버깅 강화)"""
        print(f"🔍 Img2Img: generation_completed 이벤트 수신")
        print(f"   - 이벤트 데이터: {event_data}")
        print(f"   - 탭 활성 상태: {self.is_active}")
        
        if not self.is_active:
            print(f"⚠️ 탭이 비활성 상태 - 이벤트 무시")
            return
        
        if hasattr(self, '_processing_generation') and self._processing_generation:
            print(f"⚠️ 이미 처리 중 - 중복 이벤트 무시")
            return
        
        try:
            self._processing_generation = True
            images = event_data.get('images', [])
            print(f"   - 수신된 이미지 개수: {len(images)}")
            
            if images:
                print(f"✅ 생성된 이미지 표시 시작")
                self.set_generated_image(images[0])
                print(f"✅ 생성된 이미지 표시 완료")
            else:
                print(f"⚠️ 생성된 이미지가 없음")
                
        except Exception as e:
            print(f"❌ 생성 완료 이벤트 처리 중 오류: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._processing_generation = False
    
    def on_init_image_changed(self, event_data):
        """원본 이미지 변경 이벤트 처리 (디버깅 강화)"""
        print(f"🔍 Img2Img: init_image_changed 이벤트 수신")
        print(f"   - 이벤트 데이터: {event_data}")
        print(f"   - 탭 활성 상태: {self.is_active}")
        
        if not self.is_active:
            print(f"⚠️ 탭이 비활성 상태 - 이벤트 무시")
            return
        
        if hasattr(self, '_processing_init_change') and self._processing_init_change:
            print(f"⚠️ 이미 처리 중 - 중복 이벤트 무시")
            return
        
        try:
            self._processing_init_change = True
            status = event_data.get('status')
            print(f"   - 상태: {status}")
            
            if status == 'success':
                print(f"✅ 원본 이미지 업데이트 시작")
                original_image = self.state.get_init_image()
                if original_image:
                    self.set_original_image(original_image)
                    print(f"✅ 원본 이미지 업데이트 완료")
                else:
                    print(f"⚠️ StateManager에서 원본 이미지를 찾을 수 없음")
            else:
                print(f"ℹ️ 원본 이미지 상태: {status}")
                
        except Exception as e:
            print(f"❌ 원본 이미지 변경 이벤트 처리 중 오류: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._processing_init_change = False
    
    def on_generated_images_changed(self, event_data):
        """생성된 이미지 변경 이벤트 처리 (디버깅 강화)"""
        print(f"🔍 Img2Img: generated_images_changed 이벤트 수신")
        print(f"   - 이벤트 데이터: {event_data}")
        print(f"   - 탭 활성 상태: {self.is_active}")
        
        if not self.is_active:
            print(f"⚠️ 탭이 비활성 상태 - 이벤트 무시")
            return
        
        if hasattr(self, '_processing_generated_change') and self._processing_generated_change:
            print(f"⚠️ 이미 처리 중 - 중복 이벤트 무시")
            return
        
        try:
            self._processing_generated_change = True
            count = event_data.get('count', 0)
            print(f"   - 이미지 개수: {count}")
            
            if count > 0:
                print(f"✅ 생성된 이미지 업데이트 시작")
                generated_images = self.state.get_generated_images()
                if generated_images:
                    self.set_generated_image(generated_images[0])
                    print(f"✅ 생성된 이미지 업데이트 완료")
                else:
                    print(f"⚠️ StateManager에서 생성된 이미지를 찾을 수 없음")
            else:
                print(f"ℹ️ 생성된 이미지 없음")
                
        except Exception as e:
            print(f"❌ 생성된 이미지 변경 이벤트 처리 중 오류: {e}")
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
        """일반 업로드 처리 - WebSocket 연결 중단 방지"""
        try:
            print(f"🔍 업로드 시작: 이벤트 타입={type(upload_event)}")
            
            # 파일 크기 사전 체크
            if hasattr(upload_event, 'content'):
                if hasattr(upload_event.content, 'read'):
                    # 파일 객체인 경우
                    file_data = upload_event.content.read()
                    print(f"📁 파일 크기: {len(file_data)} 바이트")
                    
                    # 크기 제한 (10MB)
                    if len(file_data) > 10 * 1024 * 1024:
                        ui.notify('파일이 너무 큽니다 (최대 10MB)', type='negative')
                        return
                else:
                    # 이미 바이트 데이터인 경우
                    file_data = upload_event.content
                    print(f"📁 바이트 데이터 크기: {len(file_data)} 바이트")
            else:
                # 구버전 호환성
                file_data = upload_event
                print(f"📁 구버전 데이터 크기: {len(file_data)} 바이트")
            
            # 이미지 로드 및 검증
            image = Image.open(io.BytesIO(file_data))
            print(f"🖼️ 이미지 로드됨: {image.size}, {image.mode}")
            
            # 이미지 유효성 검증
            if not self.validate_image(image):
                ui.notify('지원하지 않는 이미지 형식입니다', type='negative')
                return
            
            # 이미지 압축 (WebSocket 연결 중단 방지)
            optimized_image = self.optimize_image_for_upload(image)
            print(f"🔄 이미지 최적화 완료: {optimized_image.size}")
            
            # 원본 이미지 설정 (무한 재귀 방지)
            if not hasattr(self, '_uploading'):
                self._uploading = True
                self.set_original_image(optimized_image)
                self._uploading = False
                
                # 성공 알림 (UI 컨텍스트 안전하게)
                try:
                    ui.notify('이미지 업로드 완료', type='positive')
                except Exception as notify_error:
                    print(f"⚠️ 알림 표시 실패: {notify_error}")
                
                print(f"✅ 업로드 완료: {optimized_image.size}")
            else:
                print(f"⚠️ 업로드 중복 방지됨")
                
        except Exception as e:
            print(f"❌ 업로드 실패 상세: {e}")
            try:
                ui.notify(f'업로드 실패: {str(e)}', type='negative')
            except Exception as notify_error:
                print(f"⚠️ 오류 알림 표시 실패: {notify_error}")
    
    def optimize_image_for_upload(self, image: Image, max_size: int = 2048) -> Image:
        """업로드용 이미지 최적화 (WebSocket 연결 중단 방지)"""
        try:
            original_size = image.size
            print(f"🔄 이미지 최적화 시작: {original_size}")
            
            # 크기가 큰 경우 리사이즈
            if max(image.size) > max_size:
                ratio = max_size / max(image.size)
                new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
                image = image.resize(new_size, Image.Resampling.LANCZOS)
                print(f"📏 리사이즈: {original_size} → {new_size}")
            
            # RGB 변환
            if image.mode != 'RGB':
                image = image.convert('RGB')
                print(f"🎨 모드 변환: {image.mode}")
            
            # 품질 최적화
            buffer = io.BytesIO()
            image.save(buffer, format='JPEG', quality=85, optimize=True)
            optimized_image = Image.open(buffer)
            
            print(f"✅ 최적화 완료: {optimized_image.size}, {optimized_image.mode}")
            return optimized_image
            
        except Exception as e:
            print(f"❌ 이미지 최적화 중 오류: {e}")
            return image
    
    def handle_js_upload(self, data):
        """JavaScript 드래그 앤 드롭 처리 - WebSocket 연결 중단 방지"""
        try:
            print(f"🔍 JS 업로드 시작: 데이터 타입={type(data)}")
            
            # Base64 데이터 디코딩
            header, encoded = data['content'].split(',', 1)
            image_data = base64.b64decode(encoded)
            
            print(f"📁 JS 업로드 크기: {len(image_data)} 바이트")
            
            # 크기 제한 (10MB)
            if len(image_data) > 10 * 1024 * 1024:
                ui.notify('파일이 너무 큽니다 (최대 10MB)', type='negative')
                return
            
            # 이미지 로드 및 검증
            image = Image.open(io.BytesIO(image_data))
            print(f"🖼️ JS 이미지 로드됨: {image.size}, {image.mode}")
            
            # 이미지 유효성 검증
            if not self.validate_image(image):
                ui.notify('지원하지 않는 이미지 형식입니다', type='negative')
                return
            
            # 이미지 압축 (WebSocket 연결 중단 방지)
            optimized_image = self.optimize_image_for_upload(image)
            print(f"🔄 JS 이미지 최적화 완료: {optimized_image.size}")
            
            # 원본 이미지 설정 (무한 재귀 방지)
            if not hasattr(self, '_js_uploading'):
                self._js_uploading = True
                self.set_original_image(optimized_image)
                self._js_uploading = False
                
                # 성공 알림 (UI 컨텍스트 안전하게)
                try:
                    ui.notify('이미지 업로드 완료', type='positive')
                except Exception as notify_error:
                    print(f"⚠️ JS 알림 표시 실패: {notify_error}")
                
                print(f"✅ JS 업로드 완료: {optimized_image.size}")
            else:
                print(f"⚠️ JS 업로드 중복 방지됨")
                
        except Exception as e:
            print(f"❌ JS 업로드 실패: {e}")
            try:
                ui.notify(f'업로드 실패: {str(e)}', type='negative')
            except Exception as notify_error:
                print(f"⚠️ JS 오류 알림 표시 실패: {notify_error}")

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
    """업스케일 탭"""
    
    def __init__(self, state_manager: StateManager, tab_manager):
        super().__init__(state_manager, tab_manager)
        self.tab_id = 'upscale'
    
    def render(self, container):
        """업스케일 탭 렌더링"""
        with container:
            with ui.card().classes('w-full h-96 flex items-center justify-center bg-gray-800'):
                ui.label('업스케일 기능은 곧 구현됩니다').classes('text-gray-400 text-center')
    
    def activate(self):
        """탭 활성화"""
        self.is_active = True
        self.state.set('current_mode', 'upscale')
    
    def cleanup(self):
        """탭 정리"""
        self.is_active = False

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
        print(f"✅ 탭 등록: {tab_id}")
    
    def register_default_tabs(self):
        """기본 탭들 등록"""
        self.register_tab('txt2img', Txt2ImgTab)
        self.register_tab('img2img', Img2ImgTab)
        self.register_tab('inpaint', InpaintTab)
        self.register_tab('upscale', UpscaleTab)
    
    def switch_tab(self, tab_id: str):
        """탭 전환"""
        if tab_id not in self.tabs:
            print(f"❌ 존재하지 않는 탭: {tab_id}")
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
        
        print(f"🔄 탭 전환: {tab_id}")
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