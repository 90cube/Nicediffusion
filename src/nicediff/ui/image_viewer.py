"""
중앙 이미지 뷰어/캔버스 컴포넌트
"""

from nicegui import ui
from pathlib import Path
from ..core.state_manager import StateManager
import asyncio
from PIL import Image
import numpy as np
from typing import Optional, Dict, Any

class ImagePad:
    """이미지 패드 컴포넌트"""
    
    def __init__(self, state_manager: StateManager):
        self.state = state_manager
        self.current_mode = 'txt2img'
        self.current_image = None
        self.image_container = None
        self.upload_area = None
        self.status_label = None
        
        # 이벤트 구독
        self.state.subscribe('mode_changed', self._on_mode_changed)
        self.state.subscribe('image_generated', self._on_image_generated)
        self.state.subscribe('uploaded_image', self._on_uploaded_image_changed)
        
    async def render(self):
        """컴포넌트 렌더링"""
        with ui.column().classes('w-full h-full bg-gray-800 rounded-lg overflow-hidden relative') as main_container:
            self.main_container = main_container
            
            # 상단 도구바
            with ui.row().classes('absolute top-2 left-2 right-2 justify-between items-center z-10'):
                ui.label('🖼️ 이미지 패드').classes('text-white bg-black bg-opacity-50 px-3 py-1 rounded text-sm font-bold')
                ui.button(icon='refresh', on_click=self._refresh_image_pad).props('round color=white text-color=black size=sm')
            
            # 메인 이미지 영역
            with ui.element('div').classes('w-full h-full flex items-center justify-center') as image_container:
                self.image_container = image_container
                await self._show_placeholder()
            
            # 우측 하단 상태 표시 (생성 완료 등)
            with ui.row().classes('absolute bottom-2 right-2 z-10'):
                self.status_label = ui.label('준비됨').classes('text-white text-sm bg-gray-800 px-2 py-1 rounded')
    
    async def _show_placeholder(self):
        """플레이스홀더 표시"""
        current_mode = self.state.get('current_mode', 'txt2img')
        
        if current_mode in ['img2img', 'inpaint', 'upscale']:
            await self._show_upload_area()
        else:
            # t2i 모드 - 생성 대기 메시지
            if self.image_container:
                try:
                    self.image_container.clear()
                except RuntimeError as e:
                    if "deleted" in str(e).lower():
                        print("⚠️ 클라이언트가 삭제되었습니다. 플레이스홀더 표시를 건너뜁니다.")
                        return
                    else:
                        raise e
                with self.image_container:
                    with ui.card().classes('bg-gray-700 p-8 rounded-lg text-center'):
                        ui.icon('auto_awesome', size='64px').classes('text-yellow-400 mb-4')
                        ui.label('이미지 생성 대기').classes('text-white text-lg mb-2')
                        ui.label('생성 버튼을 클릭하여 이미지를 생성하세요').classes('text-gray-300 text-sm')
    
    async def _show_upload_area(self):
        """업로드 영역 표시"""
        if self.image_container:
            # 기존 내용 제거
            try:
                self.image_container.clear()
            except RuntimeError as e:
                if "deleted" in str(e).lower():
                    print("⚠️ 클라이언트가 삭제되었습니다. 업로드 영역 표시를 건너뜁니다.")
                    return
                else:
                    raise e
            
            with self.image_container:
                # 업로드 영역
                with ui.card().classes('bg-gray-700 p-8 rounded-lg text-center') as upload_card:
                    self.upload_area = upload_card
                    
                    ui.icon('cloud_upload', size='64px').classes('text-blue-400 mb-4')
                    ui.label('이미지를 드래그하거나 클릭하여 업로드').classes('text-white text-lg mb-2')
                    ui.label('PNG, JPG, JPEG, BMP, GIF, TIFF, WEBP 지원').classes('text-gray-300 text-sm mb-4')
                    
                    # 파일 업로드 버튼
                    with ui.upload(
                        on_upload=self._on_file_uploaded,
                        auto_upload=True,
                        multiple=False
                    ).classes('w-full').props('accept="image/*"'):
                        ui.button('📁 파일 선택', icon='folder_open').classes('bg-blue-500 hover:bg-blue-600 text-white px-6 py-2 rounded-lg')
    
    async def _on_file_uploaded(self, e):
        """파일 업로드 처리"""
        try:
            print(f"🔍 업로드 이벤트 타입: {type(e)}")
            print(f"🔍 업로드 이벤트 속성: {dir(e)}")
            
            # NiceGUI 파일 업로드 이벤트 처리
            if hasattr(e, 'content'):
                content = e.content
                name = e.name if hasattr(e, 'name') else 'uploaded_image'
            elif hasattr(e, 'sender') and hasattr(e.sender, 'value'):
                # 구버전 호환성
                content = e.sender.value
                name = 'uploaded_image'
            else:
                print(f"❌ 지원되지 않는 업로드 이벤트 형식: {e}")
                return
            
            print(f"🔍 파일명: {name}")
            print(f"🔍 콘텐츠 타입: {type(content)}")
            
            if content:
                # 파일 내용 읽기
                if hasattr(content, 'read'):
                    # 파일 객체인 경우
                    print("📖 파일 객체에서 읽기 중...")
                    file_data = content.read()
                    print(f"📖 읽은 데이터 크기: {len(file_data)} bytes")
                else:
                    # 이미 바이트 데이터인 경우
                    print("📖 바이트 데이터 사용 중...")
                    file_data = content
                
                # PIL 이미지로 변환
                from PIL import Image
                import io
                image = Image.open(io.BytesIO(file_data))
                print(f"✅ 이미지 로드 성공: {image.size}")
                
                # 상태 업데이트
                self.state.set('init_image', image)
                self.state.set('uploaded_image', np.array(image))
                
                # 이미지 표시
                await self._show_uploaded_image(image, name)
                
                ui.notify('이미지가 업로드되었습니다', type='positive')
                print("✅ 이미지 업로드 완료")
                
        except Exception as e:
            print(f"❌ 업로드 실패: {e}")
            import traceback
            traceback.print_exc()
            ui.notify(f'업로드 실패: {str(e)}', type='negative')
    
    async def _show_uploaded_image(self, pil_image, file_name: str):
        """업로드된 이미지 표시"""
        if self.image_container:
            try:
                # 기존 내용 제거 (클라이언트 삭제 오류 방지)
                self.image_container.clear()
            except RuntimeError as e:
                if "deleted" in str(e).lower():
                    print("⚠️ 클라이언트가 삭제되었습니다. 이미지 표시를 건너뜁니다.")
                    return
                else:
                    raise e
            
            with self.image_container:
                # 이미지를 더 큰 영역에 표시 (카드 제거)
                with ui.column().classes('w-full h-full items-center justify-center p-4'):
                    # 이미지 표시 (더 큰 크기로)
                    ui.image(pil_image).classes('max-w-full max-h-full object-contain rounded-lg shadow-lg')
                    
                    # 하단 정보 영역
                    with ui.row().classes('w-full justify-between items-center mt-4'):
                        # 파일 정보
                        ui.label(f'📁 {file_name}').classes('text-white text-sm')
                        ui.label(f'크기: {pil_image.size[0]} x {pil_image.size[1]}').classes('text-gray-300 text-xs')
                        
                        # 이미지 변경 버튼
                        ui.button('🔄 이미지 변경', on_click=self._remove_image).classes('bg-orange-500 hover:bg-orange-600 text-white text-sm px-3 py-1 rounded')
    
    async def _remove_image(self):
        """이미지 제거"""
        self.state.set('init_image', None)
        self.state.set('uploaded_image', None)
        await self._show_placeholder()
        ui.notify('이미지가 제거되었습니다', type='info')
    
    async def _on_mode_changed(self, data: dict):
        """모드 변경 이벤트 처리"""
        mode = data.get('mode', 'txt2img')
        self.current_mode = mode
        
        # t2i에서 i2i로 전환 시 생성된 이미지를 init_image로 설정
        if mode in ['img2img', 'inpaint'] and self.current_image:
            self.state.set('init_image', self.current_image)
        
        # UI 새로고침
        await self._show_placeholder()
        
        print(f"🔄 모드 변경: {mode}")
    
    async def _on_generation_started(self, data: dict):
        """생성 시작 이벤트 처리"""
        if self.status_label:
            self.status_label.text = '생성 중...'
            self.status_label.classes('text-yellow-400')
    
    async def _on_image_generated(self, data):
        """이미지 생성 완료 이벤트 처리"""
        try:
            # data가 딕셔너리인지 확인
            if isinstance(data, dict):
                image_path = data.get('image_path')
                if image_path and Path(image_path).exists():
                    await self._show_generated_image(image_path)
                    
                    # 생성된 이미지를 last_generated_images에 저장 (i2i 전환용)
                    from PIL import Image
                    pil_image = Image.open(image_path)
                    self.current_image = pil_image
                    self.state.set('last_generated_images', [pil_image])
                    
                    # 상태 업데이트
                    if self.status_label:
                        self.status_label.text = '생성 완료'
                        self.status_label.classes('text-green-400')
            else:
                print(f"⚠️ 예상하지 못한 데이터 형식: {type(data)}")
                    
        except Exception as e:
            print(f"❌ 생성된 이미지 표시 실패: {e}")
            import traceback
            traceback.print_exc()
    
    async def _on_uploaded_image_changed(self, np_image):
        """업로드된 이미지 변경 이벤트 처리"""
        if np_image is not None:
            from PIL import Image
            pil_image = Image.fromarray(np_image)
            await self._show_uploaded_image(pil_image, "업로드된 이미지")
    
    async def _show_generated_image(self, image_path: str):
        """생성된 이미지 표시"""
        if self.image_container:
            try:
                # 기존 내용 제거 (클라이언트 삭제 오류 방지)
                self.image_container.clear()
            except RuntimeError as e:
                if "deleted" in str(e).lower():
                    print("⚠️ 클라이언트가 삭제되었습니다. 이미지 표시를 건너뜁니다.")
                    return
                else:
                    raise e
            
            with self.image_container:
                # 이미지를 더 큰 영역에 표시 (카드 제거)
                with ui.column().classes('w-full h-full items-center justify-center p-4'):
                    # 이미지 표시 (더 큰 크기로)
                    ui.image(image_path).classes('max-w-full max-h-full object-contain rounded-lg shadow-lg')
                    
                    # 하단 정보 영역
                    with ui.row().classes('w-full justify-between items-center mt-4'):
                        # 파일 정보
                        file_name = Path(image_path).name
                        ui.label(f'🎨 {file_name}').classes('text-white text-sm')
                        
                        # 복사 버튼
                        ui.button('📋 클립보드 복사', on_click=lambda: self._copy_to_clipboard(image_path)).classes('bg-blue-500 hover:bg-blue-600 text-white text-sm px-3 py-1 rounded')
    
    async def _copy_to_clipboard(self, image_path: str):
        """이미지를 클립보드에 복사"""
        try:
            import pyperclip
            from PIL import Image
            import io
            import base64
            
            # 이미지를 base64로 인코딩
            image = Image.open(image_path)
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            img_str = base64.b64encode(buffer.getvalue()).decode()
            
            # 클립보드에 복사
            pyperclip.copy(f'data:image/png;base64,{img_str}')
            ui.notify('이미지가 클립보드에 복사되었습니다', type='positive')
            
        except Exception as e:
            print(f"❌ 클립보드 복사 실패: {e}")
            ui.notify('클립보드 복사에 실패했습니다', type='negative')
    
    async def _refresh_image_pad(self):
        """이미지 패드 새로고침"""
        await self._show_placeholder()
        ui.notify('이미지 패드가 새로고침되었습니다', type='info')
    
    def get_uploaded_image(self) -> Optional[np.ndarray]:
        """업로드된 이미지 반환"""
        return self.state.get('uploaded_image')
    
    def get_uploaded_image_resized(self, width: int, height: int) -> Optional[np.ndarray]:
        """리사이즈된 업로드 이미지 반환"""
        image = self.get_uploaded_image()
        if image is not None:
            from PIL import Image
            pil_image = Image.fromarray(image)
            resized = pil_image.resize((width, height), Image.Resampling.LANCZOS)
            return np.array(resized)
        return None

