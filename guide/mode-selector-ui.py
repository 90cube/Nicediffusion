# parameter_panel.py의 render_mode_selector 메서드 개선

async def render_mode_selector(self):
    """모드 선택 버튼 그룹 (개선된 버전)"""
    current_mode = self.state.get('current_mode', 'txt2img')
    
    with ui.card().classes('w-full bg-gray-900 p-3 mb-4'):
        # 모드 타이틀
        ui.label('🎨 생성 모드').classes('text-lg font-bold mb-2')
        
        # 모드 버튼 그룹 (더 크고 명확하게)
        with ui.row().classes('w-full gap-2'):
            # Text to Image
            with ui.column().classes('flex-1'):
                ui.button(
                    '✨ Text to Image',
                    on_click=lambda: self._on_mode_button_click('txt2img')
                ).classes(
                    f'w-full h-20 text-center transition-all ' +
                    ('bg-blue-600 text-white shadow-lg transform scale-105' if current_mode == 'txt2img' 
                     else 'bg-gray-700 hover:bg-gray-600')
                )
                ui.label('텍스트로 이미지 생성').classes('text-xs text-center mt-1 text-gray-400')
            
            # Image to Image
            with ui.column().classes('flex-1'):
                ui.button(
                    '🖼️ Image to Image',
                    on_click=lambda: self._on_mode_button_click('img2img')
                ).classes(
                    f'w-full h-20 text-center transition-all ' +
                    ('bg-green-600 text-white shadow-lg transform scale-105' if current_mode == 'img2img' 
                     else 'bg-gray-700 hover:bg-gray-600')
                )
                ui.label('이미지 변환/수정').classes('text-xs text-center mt-1 text-gray-400')
                
                # 이미지 업로드 상태 표시
                if current_mode == 'img2img':
                    init_image = self.state.get('init_image')
                    if init_image is None:
                        ui.icon('warning').classes('text-yellow-500 text-sm')
                        ui.label('이미지를 업로드하세요').classes('text-xs text-yellow-500')
            
            # Inpaint
            with ui.column().classes('flex-1'):
                ui.button(
                    '🎭 Inpaint',
                    on_click=lambda: self._on_mode_button_click('inpaint')
                ).classes(
                    f'w-full h-20 text-center transition-all ' +
                    ('bg-purple-600 text-white shadow-lg transform scale-105' if current_mode == 'inpaint' 
                     else 'bg-gray-700 hover:bg-gray-600')
                )
                ui.label('부분 수정').classes('text-xs text-center mt-1 text-gray-400')