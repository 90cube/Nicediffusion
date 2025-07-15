"""
중앙 이미지 뷰어/캔버스 컴포넌트 (단순화된 버전)
"""

from nicegui import ui
from pathlib import Path
from ..core.state_manager import StateManager
import asyncio
from PIL import Image
import numpy as np
from typing import Optional, Dict, Any
import json
import base64
import io

class ImagePad:
    """이미지 패드 (단순화된 버전)"""
    
    def __init__(self, state_manager: StateManager):
        self.state = state_manager
        self.current_mode = 'txt2img'
        self.current_image = None
        self.image_container = None
        self.upload_area = None
        self.status_label = None
        
        # 이벤트 구독
        self.state.subscribe('current_mode', self._on_mode_changed)
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
            with ui.column().classes('w-full h-full flex items-center justify-center') as image_container:
                self.image_container = image_container
                await self._show_placeholder()
            
            # 하단 버튼들
            with ui.row().classes('absolute bottom-4 left-1/2 transform -translate-x-1/2 gap-2'):
                ui.button('📁 이미지 선택', on_click=self._open_file_dialog).classes('bg-blue-500 text-white px-4 py-2 text-sm rounded')
                ui.button('🗑️ 이미지 제거', on_click=self._remove_image).classes('bg-red-500 text-white px-4 py-2 text-sm rounded')
                
            # 우측 상단 상태 표시
            with ui.row().classes('absolute top-2 right-2 z-10'):
                self.status_label = ui.label('준비됨').classes('text-white text-sm bg-gray-800 px-2 py-1 rounded')

    async def _show_placeholder(self):
        """플레이스홀더 표시"""
        if self.image_container:
            self.image_container.clear()
            
            with self.image_container:
                current_mode = self.state.get('current_mode', 'txt2img')
                
                if current_mode in ['img2img', 'inpaint', 'upscale']:
                    # 업로드 영역 표시
                    await self._show_upload_area()
                else:
                    # 생성된 이미지 대기 영역
                    ui.html('''
                        <div style="text-align:center;color:white;padding:40px;">
                            <div style="font-size:64px;margin-bottom:20px;">🎨</div>
                            <div style="font-size:24px;margin-bottom:10px;">이미지 생성 대기</div>
                            <div style="font-size:16px;color:#888;">
                                생성 버튼을 클릭하여 이미지를 생성하세요
                            </div>
                        </div>
                    ''')

    async def _show_upload_area(self):
        """업로드 영역 표시"""
        if self.image_container:
            self.image_container.clear()
            
            with self.image_container:
                # 드래그 앤 드롭 영역
                with ui.upload(
                    label='🖼️ 이미지를 여기에 드래그하거나 클릭하여 선택하세요',
                    on_upload=self._on_file_uploaded,
                    multiple=False
                ).classes('w-full h-full border-2 border-dashed border-gray-400 rounded-lg flex items-center justify-center bg-gray-700') as upload:
                    self.upload_area = upload
                    
                    # 안내 텍스트
                    ui.html('''
                        <div style="text-align:center;color:white;padding:40px;">
                            <div style="font-size:48px;margin-bottom:20px;">📁</div>
                            <div style="font-size:20px;margin-bottom:10px;">이미지 업로드</div>
                            <div style="font-size:14px;color:#888;margin-bottom:20px;">
                                이미지를 드래그하거나 클릭하여 선택하세요
                            </div>
                            <div style="font-size:12px;color:#666;">
                                • PNG, JPG, JPEG, BMP, GIF, TIFF, WEBP 지원<br>
                                • 최대 파일 크기: 50MB
                            </div>
                        </div>
                    ''')

    async def _on_file_uploaded(self, e):
        """파일 업로드 이벤트 처리"""
        try:
            print(f"🎉 파일 업로드: {e.name}")
            
            # 파일 데이터를 PIL Image로 변환
            file_content = e.content.read()
            pil_image = Image.open(io.BytesIO(file_content))
            
            # RGBA로 변환
            if pil_image.mode != 'RGBA':
                pil_image = pil_image.convert('RGBA')
            
            # numpy array로 변환
            np_image = np.array(pil_image)
            
            # 상태 업데이트
            self.current_image = np_image
            
            # UI 업데이트
            await self._show_uploaded_image(pil_image, e.name)
            
            # 메인 프로그램 상태 업데이트
            self.state.set('uploaded_image', np_image)
            self.state.set('init_image', np_image)
            self.state.set('init_image_path', e.name)
            
            # 상태 업데이트
            if self.status_label:
                self.status_label.text = f"이미지 로드됨: {e.name} ({np_image.shape[1]}×{np_image.shape[0]})"
            
            print(f"✅ 이미지 업로드 완료: {np_image.shape}")
            
        except Exception as e:
            error_msg = f"이미지 업로드 실패: {str(e)}"
            print(f"❌ {error_msg}")
            ui.notify(error_msg, type='negative')
            
            if self.status_label:
                self.status_label.text = "업로드 실패"

    async def _show_uploaded_image(self, pil_image, file_name: str):
        """업로드된 이미지 표시"""
        try:
            if self.image_container:
                self.image_container.clear()
                
                with self.image_container:
                    # 이미지 크기 조정 (최대 400x400)
                    max_size = 400
                    width, height = pil_image.size
                    
                    if width > max_size or height > max_size:
                        ratio = min(max_size / width, max_size / height)
                        new_width = int(width * ratio)
                        new_height = int(height * ratio)
                        pil_image = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    
                    # PIL 이미지를 base64로 변환
                    buffer = io.BytesIO()
                    pil_image.save(buffer, format='PNG')
                    img_base64 = base64.b64encode(buffer.getvalue()).decode()
                    
                    # 이미지 표시
                    ui.html(f'''
                        <div style="text-align:center;">
                            <img src="data:image/png;base64,{img_base64}" 
                                 style="max-width:100%;max-height:100%;border-radius:8px;box-shadow:0 4px 8px rgba(0,0,0,0.3);" />
                            <div style="margin-top:10px;color:white;font-size:14px;">
                                {file_name}
                            </div>
                            <div style="margin-top:5px;color:#888;font-size:12px;">
                                크기: {width}×{height}
                            </div>
                        </div>
                    ''')
                    
            print(f"✅ 이미지 표시 완료: {file_name}")
            
        except Exception as e:
            print(f"❌ 이미지 표시 실패: {e}")
            ui.notify(f"이미지 표시 실패: {str(e)}", type='negative')

    async def _open_file_dialog(self):
        """파일 선택 다이얼로그 열기"""
        try:
            # 업로드 영역 클릭 트리거
            if self.upload_area:
                # JavaScript로 파일 선택 다이얼로그 열기
                await ui.run_javascript('''
                    const input = document.createElement('input');
                    input.type = 'file';
                    input.accept = '.png,.jpg,.jpeg,.bmp,.gif,.tiff,.webp';
                    input.onchange = function(e) {
                        if (e.target.files.length > 0) {
                            const file = e.target.files[0];
                            // NiceGUI upload 컴포넌트에 파일 전달
                            const uploadElement = document.querySelector('input[type="file"]');
                            if (uploadElement) {
                                uploadElement.files = e.target.files;
                                uploadElement.dispatchEvent(new Event('change', { bubbles: true }));
                            }
                        }
                    };
                    input.click();
                ''')
        except Exception as e:
            print(f"❌ 파일 다이얼로그 오류: {e}")
            ui.notify(f"파일 선택 실패: {str(e)}", type='negative')

    async def _remove_image(self):
        """이미지 제거"""
        try:
            self.current_image = None
            
            # 메인 프로그램 상태 초기화
            self.state.set('uploaded_image', None)
            self.state.set('init_image', None)
            self.state.set('init_image_path', None)
            
            # UI 업데이트
            await self._show_placeholder()
            
            # 상태 업데이트
            if self.status_label:
                self.status_label.text = "이미지 제거됨"
                
            print("✅ 이미지 제거 완료")
            
        except Exception as e:
            print(f"❌ 이미지 제거 실패: {e}")
            ui.notify(f"이미지 제거 실패: {str(e)}", type='negative')

    async def _on_mode_changed(self, mode: str):
        """모드 변경 이벤트 처리"""
        self.current_mode = mode
        await self._show_placeholder()
        print(f"🔄 모드 변경: {mode}")
        
    async def _on_generation_started(self, data: dict):
        """이미지 생성 시작 이벤트 처리"""
        try:
            # 상태 업데이트
            if self.status_label:
                self.status_label.text = "이미지 생성 중..."
                
            # 생성 중임을 나타내는 UI 표시
            if self.image_container:
                self.image_container.clear()
                
                with self.image_container:
                    ui.html('''
                        <div style="text-align:center;color:white;padding:40px;">
                            <div style="font-size:64px;margin-bottom:20px;">🎨</div>
                            <div style="font-size:24px;margin-bottom:10px;">이미지 생성 중...</div>
                            <div style="font-size:16px;color:#888;">
                                잠시만 기다려주세요
                            </div>
                        </div>
                    ''')
                    
            print("🔄 이미지 생성 시작됨")
            
        except Exception as e:
            print(f"❌ 생성 시작 이벤트 처리 실패: {e}")
            
    async def _on_image_generated(self, data: dict):
        """이미지 생성 완료 이벤트 처리"""
        image_path = data.get('image_path')
        if image_path and Path(image_path).exists():
            await self._show_generated_image(image_path)
            
    async def _on_uploaded_image_changed(self, np_image):
        """업로드된 이미지 변경 이벤트 처리"""
        if np_image is not None:
            pil_image = Image.fromarray(np_image)
            await self._show_uploaded_image(pil_image, "업로드된 이미지")
            
    async def _show_generated_image(self, image_path: str):
        """생성된 이미지 표시"""
        try:
            if self.image_container:
                self.image_container.clear()
                
                with self.image_container:
                    # 이미지 표시
                    ui.html(f'''
                        <div style="text-align:center;">
                            <img src="{image_path}" 
                                 style="max-width:100%;max-height:100%;border-radius:8px;box-shadow:0 4px 8px rgba(0,0,0,0.3);" />
                            <div style="margin-top:10px;color:white;font-size:14px;">
                                생성된 이미지
                            </div>
                        </div>
                    ''')
                    
            # 상태 업데이트
            if self.status_label:
                self.status_label.text = "이미지 생성 완료"
                
            print(f"✅ 생성된 이미지 표시 완료: {image_path}")
            
        except Exception as e:
            print(f"❌ 생성된 이미지 표시 실패: {e}")
            
    async def _refresh_image_pad(self):
        """이미지 패드 새로고침"""
        await self._show_placeholder()
        
    def get_uploaded_image(self) -> Optional[np.ndarray]:
        """업로드된 이미지 반환"""
        return self.state.get('uploaded_image')
        
    def get_uploaded_image_resized(self, width: int, height: int) -> Optional[np.ndarray]:
        """리사이즈된 업로드 이미지 반환"""
        uploaded_image = self.get_uploaded_image()
        if uploaded_image is not None:
            pil_image = Image.fromarray(uploaded_image)
            resized_image = pil_image.resize((width, height), Image.Resampling.LANCZOS)
            return np.array(resized_image)
        return None

