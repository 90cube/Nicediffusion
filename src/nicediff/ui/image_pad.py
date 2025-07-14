"""
중앙 이미지 뷰어/캔버스 컴포넌트 (캔버스 기반 재구성)
"""

from nicegui import ui
from pathlib import Path
from ..core.state_manager import StateManager
import asyncio
from PIL import Image
import numpy as np
from typing import Optional, Callable
import io
import base64

class ImagePad:
    """이미지 패드 (캔버스 기반) - I2I 제안서 스타일 개선"""
    
    def __init__(self, state_manager: StateManager):
        self.state = state_manager
        self.current_image_path = None
        self.is_processing = False
        self.display_mode = 'contain'  # contain, fill, stretch
        
        # UI 요소들
        self.main_container = None
        self.canvas_container = None
        self.canvas = None
        self.loading_spinner = None
        self.loading_label = None
        self.progress_bar = None
        self.info_label = None
        self.display_buttons = []
        self.mode_label = None
        self.refresh_button = None
        
        # I2I 제안서 스타일 개선을 위한 추가 속성
        self.input_preview = None
        self.output_element = None
        self.submit_btn = None
        self.download_btn = None
        
        # 이벤트 구독 (InferencePage에서 중앙 관리하므로 여기서는 구독하지 않음)
        # self.state.subscribe('generation_started', self._on_generation_started)
        # self.state.subscribe('image_generated', self._on_image_generated)
        
        # 필터 관련 이벤트 구독
        self.state.subscribe('image_filter_applied', self._on_filter_applied)
        self.state.subscribe('image_filter_reset', self._on_filter_reset)
    
    # I2I 제안서 스타일 메서드들 추가
    def get_image_array(self) -> Optional[np.ndarray]:
        """현재 이미지를 numpy array로 반환 (I2I 제안서 스타일)"""
        if self.state.get('init_image'):
            pil_image = self.state.get('init_image')
            return np.array(pil_image)
        return None
    
    def set_image_array(self, array: np.ndarray):
        """numpy array를 이미지로 설정 (I2I 제안서 스타일)"""
        try:
            # numpy array -> PIL Image
            if array.dtype != np.uint8:
                array = (array * 255).astype(np.uint8)
            
            pil_image = Image.fromarray(array)
            self.state.set('init_image', pil_image)
            
            # UI 업데이트
            asyncio.create_task(self._update_display_from_array(array))
            
        except Exception as e:
            print(f"❌ numpy array를 이미지로 변환 실패: {e}")
            ui.notify(f'이미지 변환 실패: {str(e)}', type='negative')
    
    async def apply_filter(self, filter_fn: Callable):
        """필터 함수 적용 (I2I 제안서 스타일)"""
        img_array = self.get_image_array()
        if img_array is not None:
            try:
                processed = filter_fn(img_array)
                self.set_image_array(processed)
                ui.notify('필터 적용 완료', type='positive')
            except Exception as e:
                print(f"❌ 필터 적용 실패: {e}")
                ui.notify(f'필터 적용 실패: {str(e)}', type='negative')
        else:
            ui.notify('적용할 이미지가 없습니다', type='warning')
    
    async def _update_display_from_array(self, array: np.ndarray):
        """numpy array로부터 UI 업데이트"""
        try:
            # numpy array -> PIL Image -> base64
            if array.dtype != np.uint8:
                array = (array * 255).astype(np.uint8)
            
            pil_img = Image.fromarray(array)
            buffer = io.BytesIO()
            pil_img.save(buffer, format='PNG')
            base64_img = base64.b64encode(buffer.getvalue()).decode()
            
            # 임시 파일로 저장하여 기존 표시 방식과 호환
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
                pil_img.save(tmp_file.name, 'PNG')
                await self._show_image(tmp_file.name)
                
        except Exception as e:
            print(f"❌ array에서 UI 업데이트 실패: {e}")
    
    def create_gradio_style_interface(self):
        """Gradio 스타일 인터페이스 생성 (I2I 제안서 스타일)"""
        with ui.card().classes('w-full max-w-4xl mx-auto p-4'):
            ui.label('이미지 처리').classes('text-2xl font-bold mb-4')
            
            with ui.row().classes('w-full gap-4'):
                # Input column
                with ui.column().classes('flex-1'):
                    ui.label('입력 이미지').classes('text-lg font-semibold mb-2')
                    
                    # 이미지 미리보기
                    self.input_preview = ui.image().classes('w-full h-64 object-contain bg-gray-100 rounded mb-2')
                    
                    # 업로드 버튼
                    self.upload = ui.upload(
                        on_upload=self._handle_gradio_style_upload,
                        accept='image/*',
                        auto_upload=True
                    ).props('outlined')
                    
                    # 추가 입력 옵션
                    with ui.row().classes('gap-2 mt-2'):
                        ui.button('Clear', on_click=self._clear_input).props('outline')
                        ui.button('Example', on_click=self._load_example).props('outline')
                
                # Output column
                with ui.column().classes('flex-1'):
                    ui.label('출력 이미지').classes('text-lg font-semibold mb-2')
                    
                    self.output_element = ui.image().classes('w-full h-64 object-contain bg-gray-100 rounded')
                    
                    # 출력 옵션
                    with ui.row().classes('gap-2 mt-2'):
                        self.download_btn = ui.button('Download', on_click=self._download_output).props('outline')
                        if self.download_btn:
                            self.download_btn.set_enabled(False)
            
            # Submit 버튼
            self.submit_btn = ui.button('Submit', on_click=self._process_gradio_style).props('unelevated').classes('w-full mt-4')
            if self.submit_btn:
                self.submit_btn.set_enabled(False)
    
    async def _handle_gradio_style_upload(self, e):
        """Gradio 스타일 이미지 업로드 처리"""
        try:
            # 이미지를 numpy array로 변환
            pil_image = Image.open(io.BytesIO(e.content))
            self.input_array = np.array(pil_image)
            
            # StateManager에 저장
            self.state.set('init_image', pil_image)
            
            # 미리보기 업데이트
            await self._update_preview(e.content)
            
            # 버튼 활성화
            if self.submit_btn:
                self.submit_btn.set_enabled(True)
            
        except Exception as ex:
            ui.notify(f'Error: {str(ex)}', type='negative')
    
    async def _update_preview(self, image_bytes):
        """입력 이미지 미리보기 업데이트"""
        if self.input_preview:
            base64_img = base64.b64encode(image_bytes).decode()
            self.input_preview.set_source(f'data:image/png;base64,{base64_img}')
    
    async def _process_gradio_style(self):
        """Gradio 스타일 이미지 처리 실행"""
        if hasattr(self, 'input_array'):
            try:
                # 현재 모드에 따른 처리
                current_mode = self.state.get('current_mode', 'txt2img')
                
                if current_mode == 'img2img':
                    # img2img 처리 로직
                    await self._trigger_img2img_generation()
                else:
                    # 기본 이미지 처리
                    output_array = self.input_array  # 기본적으로는 그대로
                    
                    # 결과를 이미지로 변환
                    if isinstance(output_array, np.ndarray):
                        # 정규화
                        if output_array.max() > 1.0:
                            output_array = output_array.astype(np.uint8)
                        else:
                            output_array = (output_array * 255).astype(np.uint8)
                        
                        # PIL 이미지로 변환
                        output_pil = Image.fromarray(output_array)
                        
                        # base64로 인코딩
                        buffer = io.BytesIO()
                        output_pil.save(buffer, format='PNG')
                        self.output_bytes = buffer.getvalue()
                        base64_output = base64.b64encode(self.output_bytes).decode()
                        
                        # 출력 업데이트
                        if self.output_element:
                            self.output_element.set_source(f'data:image/png;base64,{base64_output}')
                        if self.download_btn:
                            self.download_btn.set_enabled(True)
                        
            except Exception as ex:
                ui.notify(f'Processing error: {str(ex)}', type='negative')
    
    async def _trigger_img2img_generation(self):
        """img2img 생성 트리거"""
        # StateManager를 통해 생성 이벤트 발생 (trigger 대신 다른 방식 사용)
        self.state.set('img2img_generation_requested', True)
        self.state.set('img2img_input_array', self.input_array)
    
    def _clear_input(self):
        """입력 이미지 클리어"""
        self.input_array = None
        if self.input_preview:
            self.input_preview.set_source('')
        if self.submit_btn:
            self.submit_btn.set_enabled(False)
        self.state.set('init_image', None)
    
    def _load_example(self):
        """예제 이미지 로드"""
        # 예제 이미지 로드 로직 (나중에 구현)
        ui.notify('예제 이미지 기능은 추후 구현 예정', type='info')
    
    def _download_output(self):
        """출력 이미지 다운로드"""
        if hasattr(self, 'output_bytes'):
            # 다운로드 로직 (나중에 구현)
            ui.notify('다운로드 기능은 추후 구현 예정', type='info')
    
    async def _on_filter_applied(self, data):
        """필터 적용 이벤트 핸들러"""
        try:
            # 현재 이미지 가져오기
            init_image = self.state.get('init_image')
            if init_image:
                # 업로드된 이미지 표시 업데이트
                await self._show_uploaded_image(init_image, "필터 적용됨")
                print(f"✅ 필터 적용 후 이미지 업데이트 완료")
            else:
                print(f"❌ 필터 적용 후 이미지를 찾을 수 없음")
        except Exception as e:
            print(f"❌ 필터 적용 이벤트 처리 실패: {e}")
    
    async def _on_filter_reset(self, data):
        """필터 초기화 이벤트 핸들러"""
        try:
            # 현재 이미지 가져오기
            init_image = self.state.get('init_image')
            if init_image:
                # 업로드된 이미지 표시 업데이트
                await self._show_uploaded_image(init_image, "필터 초기화됨")
                print(f"✅ 필터 초기화 후 이미지 업데이트 완료")
            else:
                print(f"❌ 필터 초기화 후 이미지를 찾을 수 없음")
        except Exception as e:
            print(f"❌ 필터 초기화 이벤트 처리 실패: {e}")
    
    async def render(self):
        """컴포넌트 렌더링"""
        # 메인 컨테이너
        self.main_container = ui.column().classes('w-full h-full bg-blue-900 rounded-lg overflow-hidden relative')
        
        # 초기 상태: 빈 화면
        await self._show_empty()
    
    async def _show_empty(self):
        """빈 상태 표시"""
        if self.main_container:
            self.main_container.clear()
            
            with self.main_container:
                # 상단: 모드 표시와 리프레시 버튼
                with ui.row().classes('absolute top-4 left-4 right-4 justify-between items-center z-10'):
                    # 현재 모드 표시
                    current_mode = self.state.get('current_mode', 'txt2img')
                    mode_display = {
                        'txt2img': '텍스트 → 이미지',
                        'img2img': '이미지 → 이미지',
                        'inpaint': '인페인팅',
                        'upscale': '업스케일'
                    }.get(current_mode, '텍스트 → 이미지')
                    
                    self.mode_label = ui.label(f'모드: {mode_display}').classes('text-white bg-black bg-opacity-50 px-3 py-1 rounded text-sm font-bold')
                    
                    # 리프레시 버튼
                    self.refresh_button = ui.button(
                        icon='refresh',
                        on_click=self._refresh_image_pad
                    ).props('round color=white text-color=black size=sm').tooltip('이미지 패드 새로고침')
                
                with ui.column().classes('w-full h-full items-center justify-center gap-4'):
                    ui.icon('image', size='4rem').classes('text-gray-400')
                    ui.label('이미지를 생성하거나 업로드하세요').classes('text-xl text-gray-300')
                    ui.label('텍스트 프롬프트를 입력하고 생성 버튼을 클릭하세요').classes('text-gray-400')
                    
                    # i2i 모드일 때만 이미지 업로드 영역 표시
                    current_mode = self.state.get('current_mode', 'txt2img')
                    if current_mode in ['img2img', 'inpaint', 'upscale']:
                        # 이미지 업로드 영역 (클릭 방식)
                        with ui.card().classes('w-64 h-32 border-2 border-dashed border-gray-400 hover:border-blue-400 hover:bg-blue-50 transition-colors duration-200 cursor-pointer').on('click', self._upload_image):
                            with ui.column().classes('w-full h-full items-center justify-center gap-2'):
                                ui.icon('cloud_upload', size='2rem').classes('text-gray-400')
                                ui.label('이미지를 클릭하여 업로드').classes('text-sm text-gray-500 text-center')
                                ui.label('PNG, JPG, JPEG, WEBP 지원').classes('text-xs text-gray-400')
    
    async def _show_loading(self):
        """로딩 상태 표시"""
        if self.main_container:
            self.main_container.clear()
            
            with self.main_container:
                # 상단: 모드 표시와 리프레시 버튼
                with ui.row().classes('absolute top-4 left-4 right-4 justify-between items-center z-10'):
                    current_mode = self.state.get('current_mode', 'txt2img')
                    mode_display = {
                        'txt2img': '텍스트 → 이미지',
                        'img2img': '이미지 → 이미지',
                        'inpaint': '인페인팅',
                        'upscale': '업스케일'
                    }.get(current_mode, '텍스트 → 이미지')
                    
                    self.mode_label = ui.label(f'모드: {mode_display}').classes('text-white bg-black bg-opacity-50 px-3 py-1 rounded text-sm font-bold')
                    
                    self.refresh_button = ui.button(
                        icon='refresh',
                        on_click=self._refresh_image_pad
                    ).props('round color=white text-color=black size=sm').tooltip('이미지 패드 새로고침')
                
                with ui.column().classes('w-full h-full items-center justify-center gap-4'):
                    self.loading_spinner = ui.spinner(size='lg', color='white')
                    self.loading_label = ui.label("이미지 생성 중...").classes('text-white')
                    self.progress_bar = ui.linear_progress(value=0).classes('w-64')
    
    async def _show_image(self, image_path: str):
        """이미지 표시"""
        self.current_image_path = image_path
        
        # 이미지 파일 존재 확인
        if not Path(image_path).exists():
            await self._show_error(f"이미지 파일을 찾을 수 없습니다: {image_path}")
            return
        
        self.main_container.clear()
        
        with self.main_container:
            # 상단: 모드 표시와 리프레시 버튼
            with ui.row().classes('absolute top-4 left-4 right-4 justify-between items-center z-10'):
                current_mode = self.state.get('current_mode', 'txt2img')
                mode_display = {
                    'txt2img': '텍스트 → 이미지',
                    'img2img': '이미지 → 이미지',
                    'inpaint': '인페인팅',
                    'upscale': '업스케일'
                }.get(current_mode, '텍스트 → 이미지')
                
                self.mode_label = ui.label(f'모드: {mode_display}').classes('text-white bg-black bg-opacity-50 px-3 py-1 rounded text-sm font-bold')
                
                self.refresh_button = ui.button(
                    icon='refresh',
                    on_click=self._refresh_image_pad
                ).props('round color=white text-color=black size=sm').tooltip('이미지 패드 새로고침')
            
            # 캔버스 컨테이너 (전체 화면)
            with ui.column().classes('w-full h-full relative') as self.canvas_container:
                # 캔버스 요소 (이미지 표시용)
                self.canvas = ui.html(f'''
                    <div id="image-canvas" class="w-full h-full flex items-center justify-center bg-gray-800 rounded-lg overflow-hidden">
                        <img id="display-image" src="{image_path}" 
                             class="transition-all duration-300 ease-in-out"
                             style="max-width: 100%; max-height: 100%; object-fit: contain; background-color: #374151; border-radius: 0.5rem;">
                    </div>
                ''').classes('w-full h-full')
                
                # 이미지 위에 호버 시 나타나는 도구들
                with ui.row().classes('absolute top-16 right-4 gap-2 opacity-0 hover:opacity-100 transition-opacity duration-300 z-10'):
                    ui.button(icon='fullscreen', on_click=self._show_fullscreen).props('round color=white text-color=black size=sm').tooltip('전체화면')
                    ui.button(icon='download', on_click=self._download_image).props('round color=white text-color=black size=sm').tooltip('다운로드')
                    ui.button(icon='delete', on_click=self._delete_image).props('round color=red size=sm').tooltip('삭제')
                    ui.button(icon='clear', on_click=self._remove_uploaded_image).props('round color=orange size=sm').tooltip('업로드된 이미지 제거')
                    
                    # i2i 모드일 때만 이미지 크기 적용 버튼 표시
                    current_mode = self.state.get('current_mode', 'txt2img')
                    if current_mode in ['img2img', 'inpaint', 'upscale']:
                        ui.button(
                            icon='aspect_ratio', 
                            on_click=self._apply_image_size_to_params
                        ).props('round color=blue text-color=white size=sm').tooltip('이미지 크기를 파라미터에 적용')
                
                # 이미지 정보 표시 (좌측 하단)
                try:
                    with Image.open(image_path) as img:
                        width, height = img.size
                        info_text = f'{width} × {height}'
                except Exception as e:
                    print(f"⚠️ 이미지 정보 읽기 실패: {e}")
                    info_text = '이미지 정보'
                
                self.info_label = ui.label(info_text).classes('absolute bottom-4 left-4 bg-black bg-opacity-50 rounded px-3 py-1 text-white text-sm')
                
                # 표시 방식 버튼들 (하단 중앙)
                with ui.row().classes('absolute bottom-4 left-1/2 transform -translate-x-1/2 gap-2'):
                    self.display_buttons = [
                        ui.button('Contain', on_click=lambda: self._change_display_mode('contain')).props('size=sm').classes('bg-blue-600 hover:bg-blue-700'),
                        ui.button('Fill', on_click=lambda: self._change_display_mode('fill')).props('size=sm').classes('bg-gray-600 hover:bg-gray-700'),
                        ui.button('Stretch', on_click=lambda: self._change_display_mode('stretch')).props('size=sm').classes('bg-gray-600 hover:bg-gray-700')
                    ]
                    # 기본값 활성화
                    self.display_buttons[0].classes('bg-blue-600')
        
        print(f"🎉 이미지 표시 완료: {image_path}")
    
    async def _show_error(self, message: str):
        """오류 상태 표시"""
        self.main_container.clear()
        
        with self.main_container:
            with ui.column().classes('w-full h-full items-center justify-center gap-4'):
                ui.icon('error', size='4rem').classes('text-red-400')
                ui.label(message).classes('text-xl text-red-300 text-center')
                ui.button('재시도', on_click=self._retry_generation).classes('bg-red-600 hover:bg-red-700')
    
    async def _change_display_mode(self, mode: str):
        """이미지 표시 방식 변경 (JavaScript 사용)"""
        self.display_mode = mode
        
        if self.canvas and self.current_image_path:
            # JavaScript로 직접 스타일 변경
            if mode == 'contain':
                ui.run_javascript('''
                    const img = document.getElementById('display-image');
                    if (img) {
                        img.style.objectFit = 'contain';
                        img.style.maxWidth = '100%';
                        img.style.maxHeight = '100%';
                        img.style.width = 'auto';
                        img.style.height = 'auto';
                    }
                ''')
            elif mode == 'fill':
                ui.run_javascript('''
                    const img = document.getElementById('display-image');
                    if (img) {
                        img.style.objectFit = 'cover';
                        img.style.width = '100%';
                        img.style.height = '100%';
                        img.style.maxWidth = 'none';
                        img.style.maxHeight = 'none';
                    }
                ''')
            elif mode == 'stretch':
                ui.run_javascript('''
                    const img = document.getElementById('display-image');
                    if (img) {
                        img.style.objectFit = 'fill';
                        img.style.width = '100%';
                        img.style.height = '100%';
                        img.style.maxWidth = 'none';
                        img.style.maxHeight = 'none';
                    }
                ''')
            
            # 버튼 스타일 업데이트
            for i, button in enumerate(self.display_buttons):
                if i == ['contain', 'fill', 'stretch'].index(mode):
                    button.classes('bg-blue-600')
                else:
                    button.classes('bg-gray-600')
            
            print(f"🔄 이미지 표시 방식 변경 (JS): {mode}")
            ui.notify(f'이미지 표시 방식: {mode}', type='info')
    
    async def _on_generation_started(self, data):
        """생성 시작 이벤트"""
        if self.is_processing:
            return
        
        self.is_processing = True
        await self._show_loading()
        print("🎨 생성 시작됨 - 로딩 화면 표시")
    
    async def _on_image_generated(self, data):
        """이미지 생성 완료 이벤트"""
        if not self.is_processing:
            return
        
        self.is_processing = False
        
        if isinstance(data, dict) and 'image_path' in data:
            image_path = data['image_path']
            print(f"🖼️ 이미지 생성 완료: {image_path}")
            
            # 이미지 파일 존재 확인
            if Path(image_path).exists():
                await self._show_image(image_path)
            else:
                await self._show_error(f"생성된 이미지를 찾을 수 없습니다: {image_path}")
        else:
            await self._show_error("이미지 생성 중 오류가 발생했습니다")
    
    def _show_fullscreen(self):
        """전체화면 보기"""
        if self.current_image_path:
            ui.open(self.current_image_path)
            ui.notify('전체화면으로 열렸습니다', type='info')
    
    def _download_image(self):
        """이미지 다운로드"""
        if self.current_image_path:
            ui.download(self.current_image_path)
            ui.notify('이미지 다운로드가 시작되었습니다', type='positive')
    
    def _delete_image(self):
        """이미지 삭제"""
        if self.current_image_path:
            try:
                Path(self.current_image_path).unlink()
                self.current_image_path = None
                asyncio.create_task(self._show_empty())
                ui.notify('이미지가 삭제되었습니다', type='positive')
            except Exception as e:
                ui.notify(f'이미지 삭제 실패: {e}', type='negative')
    
    async def _retry_generation(self):
        """생성 재시도"""
        await self._show_empty()
    
    async def handle_image_upload(self, image_data: str, file_name: str):
        """JavaScript에서 호출되는 이미지 업로드 처리 메서드"""
        try:
            # Base64 데이터에서 이미지 추출
            import base64
            import io
            
            # data:image/png;base64, 부분 제거
            if ',' in image_data:
                image_data = image_data.split(',')[1]
            
            # Base64 디코딩
            image_bytes = base64.b64decode(image_data)
            pil_image = Image.open(io.BytesIO(image_bytes))
            
            print(f"📸 이미지 업로드: {file_name}, 크기: {pil_image.size}")
            
            # 이미지 리사이즈 (내부적으로 처리)
            resized_image = await self._resize_image_for_generation(pil_image)
            
            # StateManager에 이미지 저장
            self.state.set('init_image', resized_image)
            
            # 업로드된 이미지 표시
            await self._show_uploaded_image(resized_image, file_name)
            
            ui.notify(f'이미지 업로드 완료: {file_name}', type='positive')
            
        except Exception as e:
            print(f"❌ 이미지 업로드 실패: {e}")
            ui.notify(f'이미지 업로드 실패: {str(e)}', type='negative')
    
    async def _resize_image_for_generation(self, pil_image):
        """생성용 이미지 리사이즈"""
        try:
            # 현재 파라미터에서 목표 크기 가져오기
            current_params = self.state.get('current_params')
            target_width = current_params.width
            target_height = current_params.height
            
            print(f"🔄 이미지 리사이즈: {pil_image.size} -> ({target_width}, {target_height})")
            
            # 고품질 리사이즈
            resized_image = pil_image.resize((target_width, target_height), Image.Resampling.LANCZOS)
            
            return resized_image
            
        except Exception as e:
            print(f"❌ 이미지 리사이즈 실패: {e}")
            return pil_image  # 원본 반환
    
    async def _show_uploaded_image(self, pil_image, file_name: str):
        """업로드된 이미지 표시 (txt2img 결과물처럼)"""
        try:
            # 임시 파일로 저장
            import tempfile
            import os
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
                pil_image.save(tmp_file.name, 'PNG')
                temp_path = tmp_file.name
            
            # 현재 이미지 경로 설정
            self.current_image_path = temp_path
            self.temp_image_path = temp_path
            
            # UI 컨테이너 초기화 및 이미지 표시
            try:
                self.main_container.clear()
                
                with self.main_container:
                    # 상단: 모드 표시와 리프레시 버튼
                    with ui.row().classes('absolute top-4 left-4 right-4 justify-between items-center z-10'):
                        current_mode = self.state.get('current_mode', 'txt2img')
                        mode_display = {
                            'txt2img': '텍스트 → 이미지',
                            'img2img': '이미지 → 이미지',
                            'inpaint': '인페인팅',
                            'upscale': '업스케일'
                        }.get(current_mode, '텍스트 → 이미지')
                        
                        self.mode_label = ui.label(f'모드: {mode_display}').classes('text-white bg-black bg-opacity-50 px-3 py-1 rounded text-sm font-bold')
                        
                        self.refresh_button = ui.button(
                            icon='refresh',
                            on_click=self._refresh_image_pad
                        ).props('round color=white text-color=black size=sm').tooltip('이미지 패드 새로고침')
                    
                    # 캔버스 컨테이너 (전체 화면)
                    with ui.column().classes('w-full h-full relative') as self.canvas_container:
                        # 캔버스 요소 (이미지 표시용)
                        self.canvas = ui.html(f'''
                            <div id="image-canvas" class="w-full h-full flex items-center justify-center bg-gray-800 rounded-lg overflow-hidden">
                                <img id="display-image" src="{temp_path}" 
                                     class="transition-all duration-300 ease-in-out"
                                     style="max-width: 100%; max-height: 100%; object-fit: contain; background-color: #374151; border-radius: 0.5rem;">
                            </div>
                        ''').classes('w-full h-full')
                        
                        # 이미지 위에 호버 시 나타나는 도구들
                        with ui.row().classes('absolute top-16 right-4 gap-2 opacity-0 hover:opacity-100 transition-opacity duration-300 z-10'):
                            ui.button(icon='fullscreen', on_click=self._show_fullscreen).props('round color=white text-color=black size=sm').tooltip('전체화면')
                            ui.button(icon='download', on_click=self._download_image).props('round color=white text-color=black size=sm').tooltip('다운로드')
                            ui.button(icon='delete', on_click=self._delete_image).props('round color=red size=sm').tooltip('삭제')
                            ui.button(icon='clear', on_click=self._remove_uploaded_image).props('round color=orange size=sm').tooltip('업로드된 이미지 제거')
                            
                            # i2i 모드일 때만 이미지 크기 적용 버튼 표시
                            current_mode = self.state.get('current_mode', 'txt2img')
                            if current_mode in ['img2img', 'inpaint', 'upscale']:
                                ui.button(
                                    icon='aspect_ratio', 
                                    on_click=self._apply_image_size_to_params
                                ).props('round color=blue text-color=white size=sm').tooltip('이미지 크기를 파라미터에 적용')
                        
                        # 이미지 정보 표시 (좌측 하단)
                        width, height = pil_image.size
                        info_text = f'{width} × {height}'
                        
                        self.info_label = ui.label(info_text).classes('absolute bottom-4 left-4 bg-black bg-opacity-50 rounded px-3 py-1 text-white text-sm')
                        
                        # 표시 방식 버튼들 (하단 중앙)
                        with ui.row().classes('absolute bottom-4 left-1/2 transform -translate-x-1/2 gap-2'):
                            self.display_buttons = [
                                ui.button('Contain', on_click=lambda: self._change_display_mode('contain')).props('size=sm').classes('bg-blue-600 hover:bg-blue-700'),
                                ui.button('Fill', on_click=lambda: self._change_display_mode('fill')).props('size=sm').classes('bg-gray-600 hover:bg-gray-700'),
                                ui.button('Stretch', on_click=lambda: self._change_display_mode('stretch')).props('size=sm').classes('bg-gray-600 hover:bg-gray-700')
                            ]
                            # 기본값 활성화
                            self.display_buttons[0].classes('bg-blue-600')
                
                print(f"✅ 업로드된 이미지 표시 완료: {file_name}")
                
            except RuntimeError as ui_error:
                if "client this element belongs to has been deleted" in str(ui_error):
                    print(f"⚠️ UI 컨텍스트 오류 무시하고 계속 진행: {ui_error}")
                    # UI 오류가 발생해도 이미지는 정상적으로 처리됨
                else:
                    raise ui_error
            
        except Exception as e:
            print(f"❌ 업로드된 이미지 표시 실패: {e}")
            # UI 오류가 아닌 경우에만 알림 표시
            if "client this element belongs to has been deleted" not in str(e):
                ui.notify(f'이미지 표시 실패: {str(e)}', type='negative')

    async def _on_file_uploaded(self, e):
        """파일 업로드 이벤트 처리 (가이드 문서 기반 개선)"""
        print(f"🎉 _on_file_uploaded 이벤트 발생!")
        print(f"🔄 파일 업로드 이벤트 발생: {getattr(e, 'name', 'N/A')}")
        print(f"🔍 업로드 이벤트 상세: 타입={type(e)}")
        print(f"🔍 이벤트 객체 속성: {dir(e)}")
        print(f"🔍 이벤트 타입: {getattr(e, 'type', 'N/A')}")
        print(f"🔍 파일명: {getattr(e, 'name', 'N/A')}")
        
        try:
            if not hasattr(e, 'content') or not e.content:
                print(f"❌ 파일 내용이 없음: {getattr(e, 'name', 'N/A')}")
                ui.notify('파일 내용을 읽을 수 없습니다', type='negative')
                return
            
            # SpooledTemporaryFile 또는 bytes 모두 지원
            import io
            import tempfile
            import uuid
            from PIL import Image
            print(f"🔄 PIL Image 변환 시작...")
            if hasattr(e.content, 'read'):
                e.content.seek(0)
                image_bytes = e.content.read()
            else:
                image_bytes = e.content
            pil_image = Image.open(io.BytesIO(image_bytes))
            print(f"✅ PIL Image 변환 완료: 크기={pil_image.size}, 모드={pil_image.mode}")
            
            # 임시 파일로 저장 (가이드 문서 방식)
            temp_path = Path('temp') / f'upload_{uuid.uuid4()}.png'
            temp_path.parent.mkdir(exist_ok=True)
            pil_image.save(temp_path)
            print(f'✅ 업로드된 이미지 임시 파일 경로: {temp_path}')
            
            # StateManager에 저장 (가이드 문서 방식)
            self.state.set('init_image', pil_image)
            self.state.set('init_image_path', str(temp_path))
            self.state.set('init_image_name', getattr(e, 'name', '업로드된 이미지'))
            self.state.set('source_image_size', {
                'width': pil_image.width,
                'height': pil_image.height
            })
            print(f"✅ StateManager에 이미지 정보 저장 완료")
            print(f"🔍 저장된 이미지: {self.state.get('init_image')}")
            print(f"🔍 저장된 경로: {self.state.get('init_image_path')}")
            print(f"🔍 저장된 이름: {self.state.get('init_image_name')}")
            
            # 이미지 처리 및 UI 표시 (업로드 즉시 img pad에 표시)
            await self._process_uploaded_image(pil_image, getattr(e, 'name', '업로드된 이미지'))
            
            # 이벤트 발생 (가이드 문서 방식)
            self.state._notify('image_uploaded', {
                'path': str(temp_path),
                'size': pil_image.size,
                'mode': pil_image.mode,
                'name': getattr(e, 'name', '업로드된 이미지')
            })
            print(f"✅ 이미지 업로드 완료 및 이벤트 발생")
        
        except Exception as ex:
            print(f"❌ 파일 업로드 처리 실패: {ex}")
            import traceback
            traceback.print_exc()
            ui.notify(f'파일 업로드 처리 실패: {str(ex)}', type='negative')

    async def _upload_image(self):
        """이미지 파일 업로드 (개선된 방식)"""
        try:
            print("🔄 이미지 업로드 다이얼로그 열기...")
            
            # 파일 선택 다이얼로그 열기
            files = ui.upload(
                label='이미지 업로드',
                multiple=False,
                max_file_size=10 * 1024 * 1024  # 10MB
            ).on('upload', self._on_file_uploaded)
            
            print("✅ 파일 업로드 다이얼로그 열기 완료")
                
        except Exception as e:
            print(f"❌ 이미지 업로드 실패: {e}")
            ui.notify(f'이미지 업로드 실패: {str(e)}', type='negative')
    
    async def _process_uploaded_image(self, pil_image, file_name: str):
        """업로드된 이미지 처리 (i2i 모드용)"""
        try:
            print(f"🔄 _process_uploaded_image 시작: {file_name}")
            print(f"�� 입력 이미지 정보: 크기={pil_image.size}, 모드={pil_image.mode}, 타입={type(pil_image)}")
            
            # 1. RGBA → RGB 변환
            if pil_image.mode == 'RGBA':
                print(f"🔄 RGBA → RGB 변환 시작...")
                background = Image.new('RGB', pil_image.size, (255, 255, 255))
                background.paste(pil_image, mask=pil_image.split()[-1])
                pil_image = background
                print(f"✅ RGBA → RGB 변환 완료")
            
            # 2. 규칙 4: 크기 일치 토글에 따른 리사이즈 처리
            current_params = self.state.get('current_params')
            size_match_enabled = getattr(current_params, 'size_match_enabled', False)
            print(f"🔍 크기 일치 토글 상태: {size_match_enabled}")
            
            if size_match_enabled:
                # 크기 일치가 활성화되면 원본 크기 유지
                processed_image = pil_image
                print(f"✅ 크기 일치 활성화: 원본 크기 유지 {pil_image.size}")
            else:
                # 크기 일치가 비활성화되면 파라미터 크기로 stretch 리사이즈
                target_width = getattr(current_params, 'width', 512)
                target_height = getattr(current_params, 'height', 512)
                processed_image = pil_image.resize((target_width, target_height), Image.Resampling.LANCZOS)
                print(f"✅ 크기 일치 비활성화: 파라미터 크기로 stretch 리사이즈 {target_width}×{target_height}")
            
            # 3. StateManager에 이미지 저장 (i2i용)
            print(f"🔄 StateManager에 이미지 저장 시작...")
            print(f"🔍 저장할 이미지 정보: 크기={processed_image.size}, 모드={processed_image.mode}, 타입={type(processed_image)}")
            
            # set_init_image 호출
            self.state.set_init_image(processed_image)
            
            # 추가 정보 저장
            self.state.set('init_image_name', file_name)
            self.state.set('init_image_size', processed_image.size)
            
            # 디버그: 이미지 저장 확인
            print(f"🔄 StateManager에서 저장된 이미지 확인...")
            saved_image = self.state.get('init_image')
            print(f"🔍 StateManager.get('init_image') 결과: {saved_image}")
            if saved_image:
                print(f"🔍 저장된 이미지 크기: {saved_image.size}, 모드: {saved_image.mode}, 타입: {type(saved_image)}")
                print(f"✅ StateManager에 이미지 저장 성공!")
            else:
                print(f"❌ StateManager에 이미지 저장 실패!")
                return
            
            # 4. 업로드된 이미지 표시
            print(f"🔄 업로드된 이미지 UI 표시 시작...")
            await self._show_uploaded_image(processed_image, file_name)
            print(f"✅ 업로드된 이미지 UI 표시 완료")
            
            # 5. i2i 모드 확인 및 파라미터 자동 설정
            current_mode = self.state.get('current_mode', 'txt2img')
            print(f"🔍 현재 모드: {current_mode}")
            
            if current_mode in ['img2img', 'inpaint', 'upscale']:
                # Denoise 파라미터가 없으면 기본값 설정
                if not hasattr(current_params, 'strength') or current_params.strength is None:
                    self.state.update_param('strength', 0.8)
                    print(f"✅ i2i 모드 기본 Strength 값 설정: 0.8")
                
                # 이미지 크기 정보 표시
                width, height = processed_image.size
                
                # 크기 일치 토글이 비활성화되어 있고, 크기가 다르면 알림
                if not size_match_enabled:
                    current_width = getattr(current_params, 'width', 512)
                    current_height = getattr(current_params, 'height', 512)
                    
                    if current_width != width or current_height != height:
                        ui.notify(
                            f'i2i 이미지 준비 완료: {file_name} ({width}×{height})\n'
                            f'파라미터 크기({current_width}×{current_height})로 stretch 리사이즈되었습니다.',
                            type='info',
                            timeout=5000
                        )
                    else:
                        ui.notify(f'i2i 이미지 준비 완료: {file_name} ({width}×{height})', type='positive')
                else:
                    ui.notify(f'i2i 이미지 준비 완료: {file_name} ({width}×{height}) - 원본 크기 유지', type='positive')
            else:
                ui.notify(f'이미지 업로드 완료: {file_name}', type='positive')
            
            print(f"✅ i2i 이미지 처리 완료: {file_name}")
            
        except Exception as e:
            print(f"❌ i2i 이미지 처리 실패: {e}")
            import traceback
            traceback.print_exc()
            ui.notify(f'이미지 처리 실패: {str(e)}', type='negative')

    async def _remove_uploaded_image(self):
        """업로드된 이미지 제거 (i2i 상태 정리)"""
        try:
            # 1. 임시 파일 삭제
            if hasattr(self, 'temp_image_path') and self.temp_image_path:
                Path(self.temp_image_path).unlink()
                self.temp_image_path = None
                print(f"✅ 임시 이미지 파일 삭제 완료")
            
            # 2. StateManager에서 i2i 관련 데이터 제거
            self.state.set('init_image', None)
            self.state.set('init_image_name', None)
            self.state.set('init_image_size', None)
            
            # 3. 현재 이미지 경로 초기화
            self.current_image_path = None
            
            # 4. 빈 화면으로 전환
            await self._show_empty()
            
            # 5. 성공 알림
            ui.notify('업로드된 이미지가 제거되었습니다', type='positive')
            print(f"✅ i2i 이미지 상태 정리 완료")
            
        except Exception as e:
            print(f"❌ 업로드된 이미지 제거 실패: {e}")
            ui.notify(f'업로드된 이미지 제거 실패: {e}', type='negative')
    
    def _apply_image_size_to_params(self):
        """업로드된 이미지의 크기를 파라미터에 적용"""
        try:
            print(f"🔄 이미지 크기 파라미터 적용 시작...")
            
            # 현재 업로드된 이미지 가져오기
            init_image = self.state.get('init_image')
            if init_image is None:
                print(f"❌ 업로드된 이미지가 없음")
                ui.notify('업로드된 이미지가 없습니다', type='warning')
                return
            
            # 이미지 크기 가져오기
            width, height = init_image.size
            print(f"🔍 이미지 크기: {width}×{height}")
            
            # StateManager를 통해 파라미터 업데이트
            self.state.update_param('width', width)
            self.state.update_param('height', height)
            
            # 성공 알림
            ui.notify(f'이미지 크기가 파라미터에 적용되었습니다: {width}×{height}', type='positive')
            print(f"✅ 이미지 크기 파라미터 적용 완료: {width}×{height}")
            
        except Exception as e:
            print(f"❌ 이미지 크기 파라미터 적용 실패: {e}")
            import traceback
            traceback.print_exc()
            ui.notify(f'이미지 크기 적용 실패: {e}', type='negative')
    


    async def _refresh_image_pad(self):
        """이미지 패드 새로고침"""
        print("🔄 이미지 패드 새로고침 중...")
        
        # 현재 모드 확인
        current_mode = self.state.get('current_mode', 'txt2img')
        
        # 현재 상태에 따라 적절한 화면 표시
        if self.current_image_path and Path(self.current_image_path).exists():
            await self._show_image(self.current_image_path)
        elif self.is_processing:
            await self._show_loading()
        else:
            # img2img 모드에서는 업로드 영역 표시
            if current_mode in ['img2img', 'inpaint', 'upscale']:
                # 업로드된 이미지가 있는지 확인
                init_image = self.state.get('init_image')
                if init_image:
                    # 업로드된 이미지가 있으면 표시
                    await self._show_uploaded_image(init_image, self.state.get('init_image_name', '업로드된 이미지'))
                else:
                    # 업로드된 이미지가 없으면 업로드 영역 표시
                    await self._show_upload_area()
            else:
                await self._show_empty()
        
        # 모드 표시 업데이트
        if self.mode_label:
            mode_display = {
                'txt2img': '텍스트 → 이미지',
                'img2img': '이미지 → 이미지',
                'inpaint': '인페인팅',
                'upscale': '업스케일'
            }.get(current_mode, '텍스트 → 이미지')
            self.mode_label.set_text(f'모드: {mode_display}')
        
        print(f"✅ 이미지 패드 새로고침 완료: {current_mode} 모드")
    
    async def _show_upload_area(self):
        """업로드 영역 표시 (i2i 모드용, JS 없이 NiceGUI upload만 사용)"""
        print(f"🔄 _show_upload_area 시작")
        if self.main_container:
            self.main_container.clear()
            
            with self.main_container:
                # 상단: 모드 표시와 리프레시 버튼
                with ui.row().classes('absolute top-4 left-4 right-4 justify-between items-center z-10'):
                    # 현재 모드 표시
                    current_mode = self.state.get('current_mode', 'txt2img')
                    mode_display = {
                        'txt2img': '텍스트 → 이미지',
                        'img2img': '이미지 → 이미지',
                        'inpaint': '인페인팅',
                        'upscale': '업스케일'
                    }.get(current_mode, '텍스트 → 이미지')
                    
                    self.mode_label = ui.label(f'모드: {mode_display}').classes('text-white bg-black bg-opacity-50 px-3 py-1 rounded text-sm font-bold')
                    
                    # 리프레시 버튼
                    self.refresh_button = ui.button(
                        icon='refresh',
                        on_click=self._refresh_image_pad
                    ).props('round color=white text-color=black size=sm').tooltip('이미지 패드 새로고침')
                
                with ui.column().classes('w-full h-full items-center justify-center gap-4'):
                    ui.icon('cloud_upload', size='4rem').classes('text-blue-400')
                    ui.label('이미지를 업로드하세요').classes('text-xl text-gray-300')
                    ui.label('img2img 모드에서 사용할 이미지를 선택하세요').classes('text-gray-400')
                    
                    # 업로드 컴포넌트 직접 배치 (NiceGUI 호환 방식)
                    print(f"🔄 업로드 컴포넌트 생성 중...")
                    self.upload_component = ui.upload(
                        on_upload=self._on_file_uploaded,
                        max_file_size=50_000_000,  # 50MB
                        auto_upload=True
                    ).props('outlined accept="image/*"').classes('w-full max-w-md')
                    
                    # 드래그 앤 드롭 영역 스타일 및 이벤트 방지
                    self.upload_component.style('''
                        border: 2px dashed #666;
                        border-radius: 8px;
                        min-height: 200px;
                        padding: 20px;
                        text-align: center;
                    ''')
                    
                    # 드래그 앤 드롭 이벤트 방지 (페이지 전체 이미지 방지)
                    ui.javascript('''
                        // 페이지 전체 드래그 앤 드롭 방지
                        document.addEventListener('dragover', function(e) {
                            e.preventDefault();
                            e.stopPropagation();
                        }, false);
                        
                        document.addEventListener('drop', function(e) {
                            e.preventDefault();
                            e.stopPropagation();
                        }, false);
                        
                        // 업로드 영역만 드래그 앤 드롭 허용
                        document.addEventListener('DOMContentLoaded', function() {
                            const uploadArea = document.querySelector('[data-testid="upload"]');
                            if (uploadArea) {
                                uploadArea.addEventListener('dragover', function(e) {
                                    e.preventDefault();
                                    e.stopPropagation();
                                    this.style.borderColor = '#3b82f6';
                                    this.style.backgroundColor = 'rgba(59, 130, 246, 0.1)';
                                });
                                
                                uploadArea.addEventListener('dragleave', function(e) {
                                    e.preventDefault();
                                    e.stopPropagation();
                                    this.style.borderColor = '#666';
                                    this.style.backgroundColor = 'transparent';
                                });
                                
                                uploadArea.addEventListener('drop', function(e) {
                                    e.preventDefault();
                                    e.stopPropagation();
                                    this.style.borderColor = '#666';
                                    this.style.backgroundColor = 'transparent';
                                });
                            }
                        });
                    ''')
                    
                    print(f"✅ 업로드 컴포넌트 생성 완료")
                    
                    # 업로드된 이미지가 있으면 표시
                    init_image = self.state.get('init_image')
                    if init_image:
                        ui.label(f'✅ 업로드된 이미지: {init_image.size[0]}×{init_image.size[1]}').classes('text-green-400 text-sm')
                
                print(f"✅ _show_upload_area 완료")

