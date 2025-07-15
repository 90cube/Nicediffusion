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
        """이미지 패드 렌더링"""
        from nicegui import ui
        
        # StateManager에서 uploaded_image 변경사항 구독
        self.state.subscribe('uploaded_image_changed', self._on_uploaded_image_changed)
        
        # 메인 컨테이너
        with ui.column().classes('w-full h-full relative'):
            # 우측 상단 캔버스 비우기 버튼
            with ui.row().classes('absolute top-2 right-2 z-10'):
                ui.button('🗑️ 캔버스 비우기', on_click=self._clear_canvas).classes('bg-red-500 text-white px-3 py-1 text-sm rounded')
            
            # 중앙 드래그앤드롭 영역 (좌우 2배 넓힘)
            with ui.column().classes('w-full h-full flex items-center justify-center'):
                upload_html = '''
                    <div style="width: 200%; max-width: 800px; padding: 40px; background: rgba(26, 26, 26, 0.9); border-radius: 12px; border: 3px dashed #4a5568; text-align: center; transition: all 0.3s; backdrop-filter: blur(10px);" id="drag-drop-area">
                        <div style="color: #a0aec0; font-size: 18px; font-weight: 500;">
                            <div style="margin-bottom: 16px; font-size: 48px;">📁</div>
                            <div style="margin-bottom: 8px;">이미지를 여기에 드래그앤드롭하세요</div>
                            <div style="font-size: 14px; color: #718096;">또는 클릭하여 파일 선택</div>
                        </div>
                    </div>
                '''
                
                # HTML 구조 렌더링
                ui.html(upload_html)
                
                # 숨겨진 파일 입력
                ui.html('<input id="api-upload-input" type="file" accept="image/*" style="display:none" />')
                
                # 업로드된 이미지 프리뷰 (작은 크기로)
                ui.html('<div id="uploaded-image-preview" style="margin-top:16px;text-align:center;max-width:300px;"></div>')
        
        # JavaScript 코드를 add_body_html로 분리
        upload_script = '''
        <script>
        // DOM이 로드된 후 실행
        document.addEventListener('DOMContentLoaded', function() {
            const uploadInput = document.getElementById('api-upload-input');
            const preview = document.getElementById('uploaded-image-preview');
            const dragDropArea = document.getElementById('drag-drop-area');
            
            let currentUploadedImage = null;
            
            // 드래그앤드롭 이벤트
            if (dragDropArea) {
                // 클릭 이벤트 (파일 선택)
                dragDropArea.addEventListener('click', function() {
                    uploadInput.click();
                });
                
                // 드래그오버 이벤트
                dragDropArea.addEventListener('dragover', function(e) {
                    e.preventDefault();
                    dragDropArea.style.borderColor = '#2563eb';
                    dragDropArea.style.background = 'rgba(30, 58, 138, 0.9)';
                    dragDropArea.style.transform = 'scale(1.02)';
                });
                
                // 드래그리브 이벤트
                dragDropArea.addEventListener('dragleave', function(e) {
                    e.preventDefault();
                    dragDropArea.style.borderColor = '#4a5568';
                    dragDropArea.style.background = 'rgba(26, 26, 26, 0.9)';
                    dragDropArea.style.transform = 'scale(1)';
                });
                
                // 드롭 이벤트
                dragDropArea.addEventListener('drop', function(e) {
                    e.preventDefault();
                    dragDropArea.style.borderColor = '#4a5568';
                    dragDropArea.style.background = 'rgba(26, 26, 26, 0.9)';
                    dragDropArea.style.transform = 'scale(1)';
                    
                    const files = e.dataTransfer.files;
                    if (files.length > 0) {
                        handleFileUpload(files[0]);
                    }
                });
            }
            
            // 파일 업로드 처리 함수
            async function handleFileUpload(file) {
                if (!file) return;
                
                // 파일 타입 검증
                if (!file.type.startsWith('image/')) {
                    preview.innerHTML = '<span style="color:red">이미지 파일만 업로드 가능합니다.</span>';
                    return;
                }
                
                // 로딩 표시
                preview.innerHTML = '<span style="color:gray">업로드 중...</span>';
                
                const formData = new FormData();
                formData.append('file', file);
                
                try {
                    const res = await fetch('/api/upload_image', {
                        method: 'POST',
                        body: formData
                    });
                    
                    if (!res.ok) {
                        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
                    }
                    
                    const data = await res.json();
                    
                    if (data.success && data.base64) {
                        currentUploadedImage = data.base64;
                        
                        // 작은 프리뷰 표시
                        preview.innerHTML = `
                            <div style="margin-top: 10px;">
                                <img src="${data.base64}" style="max-width:100%;max-height:200px;border-radius:8px;box-shadow:0 2px 8px #0003;" />
                                <p style="color:green;margin-top:8px;font-size:12px;">✅ 업로드 성공: ${data.filename}</p>
                                <p style="color:gray;font-size:11px;">크기: ${data.shape[1]}×${data.shape[0]}</p>
                            </div>
                        `;
                        
                        // 바로 Canvas에 적용
                        if (window.canvasManager && window.canvasManager.loadImageFit) {
                            window.canvasManager.loadImageFit(data.base64, 1024, 1024);
                            console.log('Canvas에 이미지 바로 적용됨');
                        }
                        
                        // 성공 메시지
                        console.log('이미지 업로드 성공:', data.filename, data.shape);
                        
                    } else {
                        preview.innerHTML = '<span style="color:red">업로드 실패: ' + (data.error || '알 수 없는 오류') + '</span>';
                    }
                } catch (error) {
                    console.error('업로드 오류:', error);
                    preview.innerHTML = '<span style="color:red">업로드 실패: ' + error.message + '</span>';
                }
            }
            
            // 파일 입력 이벤트
            if (uploadInput) {
                uploadInput.onchange = function(e) {
                    const file = e.target.files[0];
                    if (file) {
                        handleFileUpload(file);
                    }
                };
            }
        });
        </script>
        '''
        
        # JavaScript 코드를 body에 추가
        ui.add_body_html(upload_script)

    async def _clear_canvas(self):
        """캔버스 비우기"""
        from nicegui import ui
        try:
            # Canvas 비우기
            ui.run_javascript('if(window.canvasManager && window.canvasManager.clearCanvas){window.canvasManager.clearCanvas();}')
            # 프리뷰 비우기
            ui.run_javascript('document.getElementById("uploaded-image-preview").innerHTML = "";')
            # StateManager에서 이미지 제거
            self.state.set('init_image', None)
            self.state.set('uploaded_image', None)
            ui.notify('캔버스가 비워졌습니다', type='info')
        except Exception as e:
            print(f"❌ 캔버스 비우기 실패: {e}")
            ui.notify(f'캔버스 비우기 실패: {str(e)}', type='negative')

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
        """빈 상태 표시 (프리뷰/캔버스 초기화)"""
        from nicegui import ui
        ui.run_javascript('document.getElementById("uploaded-image-preview").innerHTML = "";')
        ui.run_javascript('if(window.canvasManager){window.canvasManager.loadImageFit("", 512, 512);}')

    async def _show_loading(self):
        """로딩 상태 표시 (스피너 등)"""
        from nicegui import ui
        ui.run_javascript('document.getElementById("uploaded-image-preview").innerHTML = "<span style=\"color:gray\">로딩 중...</span>";')

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

    async def _show_fullscreen(self):
        """전체화면 보기 (새 창에 이미지 표시)"""
        if self.uploaded_image is not None:
            from PIL import Image
            import io, base64
            img = Image.fromarray(self.uploaded_image)
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
            from nicegui import ui
            ui.run_javascript(f'window.open("data:image/png;base64,{b64}", "_blank")')

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
        """이미지의 가장 긴 변이 1544를 넘으면 비율을 유지하여 1544에 맞춰 축소, SDXL 최소 크기 보장"""
        width, height = pil_image.size
        max_size = 1544
        min_size = 768  # SDXL 최소 크기
        
        # 가장 긴 변이 1544를 넘는지 확인
        if width <= max_size and height <= max_size:
            # SDXL 최소 크기 보장
            if width < min_size or height < min_size:
                # 비율을 유지하면서 최소 크기로 확대
                if width < height:
                    new_height = min_size
                    new_width = int(width * (min_size / height))
                else:
                    new_width = min_size
                    new_height = int(height * (min_size / width))
                
                # 8의 배수로 조정
                new_width = new_width - (new_width % 8)
                new_height = new_height - (new_height % 8)
                
                resized_image = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                print(f"🔄 SDXL 최소 크기로 조정: {width}×{height} → {new_width}×{new_height}")
                return resized_image
            
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
        
        # 8의 배수로 조정
        new_width = new_width - (new_width % 8)
        new_height = new_height - (new_height % 8)
        
        # SDXL 최소 크기 보장
        if new_width < min_size:
            new_width = min_size
            new_height = int(height * (min_size / width))
            new_height = new_height - (new_height % 8)
        elif new_height < min_size:
            new_height = min_size
            new_width = int(width * (min_size / height))
            new_width = new_width - (new_width % 8)
        
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

    async def on_mode_changed(self, new_mode):
        """모드가 변경될 때 init_image를 자동으로 ImagePad에 표시"""
        self.current_mode = new_mode
        init_image = self.state.get('init_image')
        if init_image is not None:
            # numpy array → base64 변환 후 바로 Canvas에 적용
            from PIL import Image
            import io, base64
            img = Image.fromarray(init_image)
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
            from nicegui import ui
            ui.run_javascript(f'''
                // 프리뷰에 표시
                const preview = document.getElementById('uploaded-image-preview');
                if (preview) {{
                    preview.innerHTML = '<img src="data:image/png;base64,{b64}" style="max-width:100%;max-height:200px;border-radius:8px;box-shadow:0 2px 8px #0003;" />';
                }}
                
                // 바로 Canvas에 적용
                if (window.canvasManager && window.canvasManager.loadImageFit) {{
                    window.canvasManager.loadImageFit("data:image/png;base64,{b64}", 1024, 1024);
                }}
            ''')

    async def on_history_image_selected(self, np_image):
        """히스토리에서 이미지 선택 시 ImagePad에 자동 반영"""
        self.set_uploaded_image(np_image)
        # numpy array → base64 변환 후 바로 Canvas에 적용
        from PIL import Image
        import io, base64
        img = Image.fromarray(np_image)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        from nicegui import ui
        ui.run_javascript(f'''
            // 프리뷰에 표시
            const preview = document.getElementById('uploaded-image-preview');
            if (preview) {{
                preview.innerHTML = '<img src="data:image/png;base64,{b64}" style="max-width:100%;max-height:200px;border-radius:8px;box-shadow:0 2px 8px #0003;" />';
            }}
            
            // 바로 Canvas에 적용
            if (window.canvasManager && window.canvasManager.loadImageFit) {{
                window.canvasManager.loadImageFit("data:image/png;base64,{b64}", 1024, 1024);
            }}
        ''')

    async def _on_uploaded_image_changed(self, np_image):
        """StateManager에서 uploaded_image가 변경되었을 때 호출"""
        if np_image is not None:
            print(f"🖼️ StateManager에서 이미지 변경 감지: {np_image.shape}")
            self.uploaded_image = np_image
            
            # 이미지를 base64로 변환하여 프리뷰에 표시하고 바로 Canvas에 적용
            try:
                from PIL import Image
                import io
                import base64
                
                # numpy array를 PIL Image로 변환
                pil_image = Image.fromarray(np_image)
                
                # base64로 인코딩
                buf = io.BytesIO()
                pil_image.save(buf, format='PNG')
                b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
                
                # JavaScript로 프리뷰 업데이트 및 바로 Canvas에 적용
                ui.run_javascript(f'''
                    // 프리뷰 업데이트
                    const preview = document.getElementById('uploaded-image-preview');
                    if (preview) {{
                        preview.innerHTML = '<img src="data:image/png;base64,{b64}" style="max-width:100%;max-height:200px;border-radius:8px;box-shadow:0 2px 8px #0003;" />';
                    }}
                    
                    // 바로 Canvas에 적용
                    if (window.canvasManager && window.canvasManager.loadImageFit) {{
                        window.canvasManager.loadImageFit("data:image/png;base64,{b64}", 1024, 1024);
                    }}
                ''')
                
                print(f"✅ 이미지 프리뷰 업데이트 및 Canvas 바로 적용 완료: {np_image.shape}")
                
            except Exception as e:
                print(f"❌ 이미지 프리뷰 업데이트 실패: {e}")
                # UI 컨텍스트가 없는 경우 조용히 처리
                try:
                    ui.notify(f'이미지 표시 실패: {str(e)}', type='negative')
                except:
                    pass 