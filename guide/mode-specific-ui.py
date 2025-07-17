# image_viewer.py의 _render_mode_overlay 메서드 개선

async def _render_mode_overlay(self):
    """모드별 오버레이 UI 렌더링"""
    current_mode = self.state.get('current_mode', 'txt2img')
    
    # txt2img 모드: 업로드 UI 없음
    if current_mode == 'txt2img':
        # 생성 대기 메시지만 표시
        with ui.element('div').classes(
            'absolute inset-0 flex items-center justify-center pointer-events-none'
        ):
            # 생성된 이미지가 없을 때만 표시
            if self.current_image is None:
                with ui.card().classes('bg-gray-700 bg-opacity-50 p-8 rounded-lg'):
                    ui.icon('auto_awesome', size='64px').classes('text-yellow-400 mb-4')
                    ui.label('✨ 텍스트로 이미지를 생성하세요').classes('text-lg text-gray-300')
                    ui.label('프롬프트를 입력하고 생성 버튼을 클릭하세요').classes('text-sm text-gray-400')
    
    # img2img, inpaint, upscale 모드: 업로드 UI 표시
    elif current_mode in ['img2img', 'inpaint', 'upscale']:
        with ui.element('div').classes(
            'absolute inset-0 flex items-center justify-center'
        ) as overlay:
            self.overlay_container = overlay
            
            # 이미지가 없을 때만 업로드 UI 표시
            init_image = self.state.get('init_image')
            if init_image is None:
                # 드래그앤드롭 영역
                with ui.element('div').classes(
                    'w-full h-full flex items-center justify-center'
                ).on('dragover', self._handle_dragover).on('drop', self._handle_drop):
                    
                    with ui.card().classes(
                        'bg-gray-700 bg-opacity-90 p-12 rounded-lg border-2 border-dashed border-gray-500 hover:border-blue-500 transition-colors'
                    ):
                        # 모드별 아이콘과 메시지
                        mode_info = {
                            'img2img': ('🖼️', '이미지를 변환할 원본을 업로드하세요'),
                            'inpaint': ('🎭', '수정할 이미지를 업로드하세요'),
                            'upscale': ('🔍', '확대할 이미지를 업로드하세요')
                        }
                        icon, message = mode_info.get(current_mode, ('📁', '이미지를 업로드하세요'))
                        
                        ui.label(icon).classes('text-6xl mb-4')
                        ui.label(message).classes('text-lg mb-4 text-white')
                        
                        # 업로드 버튼
                        with ui.row().classes('gap-4'):
                            ui.upload(
                                label='파일 선택',
                                on_upload=self._handle_file_upload,
                                auto_upload=True,
                                multiple=False
                            ).props('accept="image/*" color=blue').classes('flex-1')
                            
                            # URL 입력 (선택사항)
                            ui.button(
                                'URL로 가져오기',
                                on_click=self._show_url_dialog
                            ).props('outline color=blue')
            else:
                # 이미지가 있을 때: 편집 도구 표시
                await self._render_edit_tools(current_mode)

async def _handle_dragover(self, e):
    """드래그오버 이벤트 처리"""
    e.preventDefault()
    # 시각적 피드백
    ui.run_javascript('''
        event.currentTarget.classList.add('bg-blue-900', 'bg-opacity-20');
    ''')

async def _handle_drop(self, e):
    """드롭 이벤트 처리"""
    e.preventDefault()
    # 시각적 피드백 제거
    ui.run_javascript('''
        event.currentTarget.classList.remove('bg-blue-900', 'bg-opacity-20');
    ''')
    
    # 파일 처리는 JavaScript에서 처리
    ui.run_javascript(f'''
        const files = event.dataTransfer.files;
        if (files.length > 0) {{
            const file = files[0];
            if (file.type.startsWith('image/')) {{
                // FormData로 업로드
                const formData = new FormData();
                formData.append('file', file);
                
                fetch('/api/upload_image', {{
                    method: 'POST',
                    body: formData
                }}).then(response => response.json())
                  .then(data => {{
                      if (data.success) {{
                          // Canvas에 이미지 표시
                          const img = new Image();
                          img.src = data.base64;
                          img.onload = () => {{
                              if (window.imagePadCanvas) {{
                                  drawImageFitToCanvas(img, window.imagePadCanvas.canvas, window.imagePadCanvas.ctx);
                              }}
                          }};
                      }}
                  }});
            }}
        }}
    ''')