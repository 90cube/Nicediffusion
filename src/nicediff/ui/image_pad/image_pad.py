from nicegui import ui
import numpy as np
from PIL import Image
import io
import base64
from typing import Optional
import os

class ImagePad:
    def __init__(self, state_manager):
        self.state = state_manager
        self.current_image = None
        self.current_image_path = None
        self.image_container = None
        self.upload_area = None
        self.status_label = None
        
    async def render(self):
        """이미지 패드 렌더링 - NiceGUI 내장 기능 사용"""
        from nicegui import ui
        
        # 메인 컨테이너
        with ui.column().classes('w-full h-full relative') as main_container:
            # 제목
            with ui.row().classes('absolute top-2 left-2 z-10'):
                ui.html('<h3 style="color:white;margin:0;">🖼️ 이미지 패드</h3>')
            
            # 중앙 컨테이너
            with ui.column().classes('w-full h-full flex items-center justify-center relative') as center_container:
                # 이미지 표시 영역
                with ui.column().classes('w-full h-full flex items-center justify-center') as image_container:
                    self.image_container = image_container
                    
                    # 초기 업로드 영역
                    await self._show_upload_area()
            
            # 하단 버튼들
            with ui.row().classes('absolute bottom-4 left-1/2 transform -translate-x-1/2'):
                ui.button('📁 이미지 선택', on_click=self._open_file_dialog).classes('bg-blue-500 text-white px-6 py-3 text-lg rounded-lg')
                ui.button('🗑️ 이미지 제거', on_click=self._remove_image).classes('bg-red-500 text-white px-6 py-3 text-lg rounded-lg ml-2')
                
            # 우측 상단 상태 표시
            with ui.row().classes('absolute top-2 right-2 z-10'):
                self.status_label = ui.label('준비됨').classes('text-white text-sm bg-gray-800 px-2 py-1 rounded')

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
                ).classes('w-full h-full border-2 border-dashed border-gray-400 rounded-lg flex items-center justify-center bg-gray-800') as upload:
                    self.upload_area = upload
                    
                    # 안내 텍스트
                    ui.html('''
                        <div style="text-align:center;color:white;padding:40px;">
                            <div style="font-size:64px;margin-bottom:20px;">📁</div>
                            <div style="font-size:24px;margin-bottom:10px;">이미지 업로드</div>
                            <div style="font-size:16px;color:#888;margin-bottom:30px;">
                                이미지를 드래그하거나 클릭하여 선택하세요
                            </div>
                            <div style="font-size:14px;color:#666;">
                                • PNG, JPG, JPEG, BMP, GIF, TIFF, WEBP 지원<br>
                                • 최대 파일 크기: 50MB<br>
                                • 자동으로 img2img 모드로 전환됩니다
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
            self.current_image_path = e.name
            
            # UI 업데이트
            await self._show_uploaded_image(pil_image, e.name)
            
            # 메인 프로그램 상태 업데이트
            self.state.set('uploaded_image', np_image)
            self.state.set('init_image', np_image)
            self.state.set('init_image_path', e.name)
            self.state.set('current_mode', 'img2img')
            
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
                        </div>
                    ''')
                    
                    # 이미지 정보
                    ui.html(f'''
                        <div style="margin-top:10px;color:#888;font-size:12px;">
                            크기: {width}×{height} | 모드: img2img
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
            self.current_image_path = None
            
            # 메인 프로그램 상태 초기화
            self.state.set('uploaded_image', None)
            self.state.set('init_image', None)
            self.state.set('init_image_path', None)
            
            # UI 업데이트
            await self._show_upload_area()
            
            # 상태 업데이트
            if self.status_label:
                self.status_label.text = "이미지 제거됨"
                
            ui.notify("이미지가 제거되었습니다", type='info')
            print("🗑️ 이미지 제거 완료")
            
        except Exception as e:
            print(f"❌ 이미지 제거 실패: {e}")
            ui.notify(f"이미지 제거 실패: {str(e)}", type='negative')

    # 기존 호환성 메서드들
    def set_uploaded_image(self, np_image: np.ndarray):
        """API로 받은 numpy 이미지를 ImagePad에 세팅"""
        self.current_image = np_image
        print(f"✅ 이미지 업로드 완료: {np_image.shape}")

    def get_uploaded_image(self) -> Optional[np.ndarray]:
        """현재 업로드된 이미지를 numpy array 또는 None으로 반환"""
        return self.current_image

    async def on_mode_changed(self, new_mode):
        """모드가 변경될 때 호출"""
        print(f"🔄 모드 변경: {new_mode}")

    async def on_history_image_selected(self, np_image):
        """히스토리에서 이미지 선택 시 호출"""
        self.current_image = np_image
        print(f"📸 히스토리 이미지 선택: {np_image.shape}")
        
    # 누락된 호환성 메서드들 추가
    async def _on_image_generated(self, data):
        """이미지 생성 완료 이벤트 - 호환성을 위한 빈 구현"""
        print("🖼️ 이미지 생성 완료")
        
    async def _on_generation_started(self, data):
        """생성 시작 이벤트 - 호환성을 위한 빈 구현"""
        print("🎨 생성 시작됨")
        
    def _show_empty(self):
        """빈 상태 표시 - 호환성을 위한 빈 구현"""
        print("📭 빈 상태 표시")
        
    def _show_loading(self):
        """로딩 상태 표시 - 호환성을 위한 빈 구현"""
        print("⏳ 로딩 상태 표시")
        
    def _show_image(self, image_path: str):
        """이미지 표시 - 호환성을 위한 빈 구현"""
        print(f"🖼️ 이미지 표시: {image_path}")
        
    def _show_error(self, message: str):
        """오류 상태 표시 - 호환성을 위한 빈 구현"""
        print(f"❌ 오류 표시: {message}")
        
    def _change_display_mode(self, mode: str):
        """이미지 표시 방식 변경 - 호환성을 위한 빈 구현"""
        print(f"🔄 표시 모드 변경: {mode}")
        
    def _show_fullscreen(self):
        """전체화면 보기 - 호환성을 위한 빈 구현"""
        print("⛶ 전체화면 보기")
        
    def _download_image(self):
        """이미지 다운로드 - 호환성을 위한 빈 구현"""
        print("📥 이미지 다운로드")
        
    def _delete_image(self):
        """이미지 삭제 - 호환성을 위한 빈 구현"""
        print("🗑️ 이미지 삭제")
        
    async def _retry_generation(self):
        """생성 재시도 - 호환성을 위한 빈 구현"""
        print("🔄 생성 재시도")
        
    def handle_image_upload(self, image_data: str, file_name: str):
        """JavaScript에서 호출되는 이미지 업로드 처리 메서드 - 호환성을 위한 빈 구현"""
        print(f"📸 이미지 업로드: {file_name}")
        
    async def _resize_image_for_generation(self, pil_image):
        """생성용 이미지 리사이즈 - 호환성을 위한 빈 구현"""
        return pil_image
        
    def _resize_image_to_1544_limit(self, pil_image):
        """이미지 크기 제한 - 호환성을 위한 빈 구현"""
        return pil_image
        
    async def _upload_image(self):
        """이미지 파일 업로드 - 호환성을 위한 빈 구현"""
        print("🔄 이미지 업로드 다이얼로그")
        
    async def _process_uploaded_image(self, pil_image, file_name: str):
        """업로드된 이미지 처리 - 호환성을 위한 빈 구현"""
        print(f"🔄 이미지 처리: {file_name}")
        
    async def _remove_uploaded_image(self):
        """업로드된 이미지 제거 - 호환성을 위한 빈 구현"""
        print("🗑️ 업로드된 이미지 제거")
        
    def _apply_image_size_to_params(self):
        """이미지 크기를 파라미터에 적용 - 호환성을 위한 빈 구현"""
        print("📏 이미지 크기를 파라미터에 적용")
        
    async def _refresh_image_pad(self):
        """이미지 패드 새로고침 - 호환성을 위한 빈 구현"""
        print("🔄 이미지 패드 새로고침")
        
    def get_uploaded_image_base64(self) -> str:
        """업로드된 numpy 이미지를 base64 PNG로 변환해 반환 - 호환성을 위한 빈 구현"""
        return ""
        
    def show_uploaded_image_fit(self, container_width: int, container_height: int):
        """프론트엔드 JS에 fit 표시 명령 전송 - 호환성을 위한 빈 구현"""
        print(f"🎨 이미지 fit 표시: {container_width}x{container_height}")
        
    def add_image_layer(self):
        """레이어 시스템에 업로드 이미지를 배경/이미지 레이어로 추가 - 호환성을 위한 빈 구현"""
        print("🎨 이미지 레이어 추가") 