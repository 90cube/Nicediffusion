from .mode_handlers.view_handler import ViewModeHandler
from .mode_handlers.img2img_handler import Img2ImgHandler
from .mode_handlers.inpaint_handler import InpaintHandler
import numpy as np
from typing import Optional
import base64
import io
from PIL import Image
from nicegui import ui
from pathlib import Path
import asyncio

class ImagePad:
    def __init__(self, state_manager):
        self.state = state_manager
        self.current_mode = 'view'
        self.layers = {}
        self.canvas_manager = None
        self.mode_handlers = {
            'view': ViewModeHandler(),
            'txt2img': None,  # 추후 구현
            'img2img': Img2ImgHandler(),
            'inpaint': InpaintHandler(),
            'upscale': None
        }
        self.uploaded_image = None  # numpy array
        
        # 기존 ImagePad 호환성을 위한 속성들
        self.current_image_path = None
        self.is_processing = False
        self.display_mode = 'contain'
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
        self.temp_image_path = None

    async def render(self):
        """기본 render 메서드 - 기존 ImagePad와 호환"""
        with ui.card().classes('w-full h-full p-4'):
            ui.label('ImagePad (새로운 구조)').classes('text-lg font-bold')
            ui.label('업로드 API: /api/upload_image').classes('text-sm text-gray-500')
            
            # 업로드 버튼 추가
            ui.button('이미지 업로드 테스트', on_click=self._test_upload).classes('bg-blue-600 text-white')

    def _test_upload(self):
        """실제 파일 업로드 기능"""
        try:
            # 파일 선택 다이얼로그 열기
            files = ui.upload(
                label='이미지 업로드',
                multiple=False
            ).on('upload', self._on_file_uploaded)
            
            ui.notify('파일을 선택해주세요', type='info')
        except Exception as e:
            ui.notify(f'업로드 실패: {e}', type='negative')

    # 기존 ImagePad 호환 메서드들 (뼈대 구현)
    async def _on_generation_started(self, data):
        """생성 시작 이벤트"""
        print("🎨 생성 시작됨")
        self.is_processing = True

    async def _on_image_generated(self, data):
        """이미지 생성 완료 이벤트"""
        print("🖼️ 이미지 생성 완료")
        self.is_processing = False

    async def _show_empty(self):
        """빈 상태 표시"""
        pass

    async def _show_loading(self):
        """로딩 상태 표시"""
        pass

    async def _show_image(self, image_path: str):
        """이미지 표시"""
        self.current_image_path = image_path
        print(f"🎉 이미지 표시: {image_path}")

    async def _show_error(self, message: str):
        """오류 상태 표시"""
        ui.notify(message, type='negative')

    async def _change_display_mode(self, mode: str):
        """이미지 표시 방식 변경"""
        self.display_mode = mode
        print(f"🔄 이미지 표시 방식 변경: {mode}")

    def _show_fullscreen(self):
        """전체화면 보기"""
        if self.current_image_path:
            ui.notify('전체화면 기능은 추후 구현 예정', type='info')

    def _download_image(self):
        """이미지 다운로드"""
        if self.current_image_path:
            ui.download(self.current_image_path)

    def _delete_image(self):
        """이미지 삭제"""
        if self.current_image_path:
            try:
                Path(self.current_image_path).unlink()
                self.current_image_path = None
                ui.notify('이미지가 삭제되었습니다', type='positive')
            except Exception as e:
                ui.notify(f'이미지 삭제 실패: {e}', type='negative')

    async def _retry_generation(self):
        """생성 재시도"""
        await self._show_empty()

    async def handle_image_upload(self, image_data: str, file_name: str):
        """JavaScript에서 호출되는 이미지 업로드 처리 메서드"""
        print(f"📸 이미지 업로드: {file_name}")

    async def _resize_image_for_generation(self, pil_image):
        """생성용 이미지 리사이즈"""
        return pil_image

    async def _show_uploaded_image(self, pil_image, file_name: str):
        """업로드된 이미지 표시"""
        print(f"✅ 업로드된 이미지 표시: {file_name}")

    async def _on_file_uploaded(self, e):
        """파일 업로드 이벤트 처리 - 1544 크기 제한 적용"""
        print(f"🎉 파일 업로드: {e.name}")
        
        try:
            if not e.content:
                print(f"❌ 파일 내용이 없음: {e.name}")
                ui.notify('파일 내용을 읽을 수 없습니다', type='negative')
                return
            
            # PIL Image로 변환
            import io
            import tempfile
            print(f"🔄 PIL Image 변환 시작...")
            pil_image = Image.open(io.BytesIO(e.content))
            print(f"✅ PIL Image 변환 완료: 크기={pil_image.size}, 모드={pil_image.mode}")
            
            # 1544 크기 제한 적용
            pil_image = self._resize_image_to_1544_limit(pil_image)
            print(f"🔄 크기 조정 완료: {pil_image.size}")
            
            # numpy array로 변환하여 저장
            np_image = np.array(pil_image)
            self.set_uploaded_image(np_image)
            
            # 임시 파일로 저장
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
            pil_image.save(temp_file.name)
            self.state.set('init_image_path', temp_file.name)
            print(f'✅ 업로드된 이미지 임시 파일 경로: {temp_file.name}')
            
            ui.notify(f'이미지 업로드 완료: {e.name} ({pil_image.size[0]}×{pil_image.size[1]})', type='positive')
            
        except Exception as e:
            print(f"❌ 파일 업로드 처리 실패: {e}")
            import traceback
            traceback.print_exc()
            ui.notify(f'파일 업로드 처리 실패: {str(e)}', type='negative')

    def _resize_image_to_1544_limit(self, pil_image):
        """이미지의 가장 긴 변이 1544를 넘으면 비율을 유지하여 1544에 맞춰 축소"""
        width, height = pil_image.size
        max_size = 1544
        
        # 가장 긴 변이 1544를 넘는지 확인
        if width <= max_size and height <= max_size:
            return pil_image  # 크기 조정 불필요
        
        # 비율 계산
        if width > height:
            # 가로가 더 긴 경우
            new_width = max_size
            new_height = int(height * (max_size / width))
        else:
            # 세로가 더 긴 경우
            new_height = max_size
            new_width = int(width * (max_size / height))
        
        # 고품질 리사이즈
        resized_image = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        print(f"🔄 이미지 크기 조정: {width}×{height} → {new_width}×{new_height}")
        
        return resized_image

    async def _upload_image(self):
        """이미지 파일 업로드"""
        print("🔄 이미지 업로드 다이얼로그")

    async def _process_uploaded_image(self, pil_image, file_name: str):
        """업로드된 이미지 처리"""
        print(f"🔄 이미지 처리: {file_name}")

    async def _remove_uploaded_image(self):
        """업로드된 이미지 제거"""
        self.uploaded_image = None
        ui.notify('업로드된 이미지가 제거되었습니다', type='info')

    def _apply_image_size_to_params(self):
        """이미지 크기를 파라미터에 적용"""
        if self.uploaded_image is not None:
            height, width = self.uploaded_image.shape[:2]
            self.state.update_param('width', width)
            self.state.update_param('height', height)
            ui.notify(f'이미지 크기를 파라미터에 적용: {width}×{height}', type='positive')

    async def _refresh_image_pad(self):
        """이미지 패드 새로고침"""
        print("🔄 이미지 패드 새로고침")

    async def _show_upload_area(self):
        """업로드 영역 표시"""
        pass

    def set_uploaded_image(self, np_image: np.ndarray):
        """API로 받은 numpy 이미지를 ImagePad에 세팅"""
        self.uploaded_image = np_image
        print(f"✅ 이미지 업로드 완료: {np_image.shape}")

    def get_uploaded_image(self) -> Optional[np.ndarray]:
        """현재 업로드된 이미지를 numpy array 또는 None으로 반환"""
        return self.uploaded_image

    def get_uploaded_image_base64(self) -> str:
        """업로드된 numpy 이미지를 base64 PNG로 변환해 반환"""
        if self.uploaded_image is None:
            return ''
        img = Image.fromarray(self.uploaded_image)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        return f'data:image/png;base64,{b64}'

    def show_uploaded_image_fit(self, container_width: int, container_height: int):
        """프론트엔드 JS에 fit 표시 명령 전송 (NiceGUI run_javascript 사용)"""
        b64img = self.get_uploaded_image_base64()
        ui.run_javascript(f'window.canvasManager.loadImageFit("{b64img}", {container_width}, {container_height})')

    def add_image_layer(self):
        """레이어 시스템에 업로드 이미지를 배경/이미지 레이어로 추가 (뼈대)"""
        if self.uploaded_image is not None:
            self.layers['image'] = self.uploaded_image 