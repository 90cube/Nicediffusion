from nicegui import ui
from nicegui.events import UploadEventArguments

# 전역 변수로 이미지 소스와 현재 모드 저장
image_source = None
current_mode = 'fit'

def handle_upload(e: UploadEventArguments):
    global image_source
    # 업로드된 파일을 base64로 변환하여 저장
    image_source = e.content.read()
    # 이미지 업데이트
    update_image()

def update_image():
    if image_source:
        # 현재 모드에 따라 이미지 스타일 적용
        if current_mode == 'fit':
            # 비율 유지하면서 영역에 맞춤
            image.set_source(image_source)
            image.classes(remove='w-full h-full', add='max-w-full max-h-full object-contain')
        elif current_mode == 'full':
            # 이미지가 잘리더라도 영역을 꽉 채움
            image.set_source(image_source)
            image.classes(remove='max-w-full max-h-full object-contain', add='w-full h-full object-cover')
        elif current_mode == 'stretch':
            # 비율 무시하고 영역에 딱 맞춤
            image.set_source(image_source)
            image.classes(remove='max-w-full max-h-full object-contain object-cover', add='w-full h-full object-fill')

def set_mode(mode: str):
    global current_mode
    current_mode = mode
    update_image()

# 메인 컨테이너
with ui.column().classes('w-full items-center gap-4 p-4'):
    # 이미지 업로드 버튼
    ui.upload(on_upload=handle_upload).props('accept=image/*').classes('mb-4')
    
    # 16:9 비율의 이미지 표시 영역
    with ui.card().classes('w-full max-w-3xl'):
        # 16:9 비율 유지를 위한 컨테이너
        with ui.element('div').classes('relative w-full pb-[56.25%] bg-gray-100'):
            # 절대 위치로 이미지 컨테이너 설정
            with ui.element('div').classes('absolute inset-0 flex items-center justify-center'):
                image = ui.image().classes('max-w-full max-h-full object-contain')
    
    # 이미지 표시 모드 버튼들
    with ui.row().classes('gap-2'):
        ui.button('Fit', on_click=lambda: set_mode('fit')).props('size=sm color=primary')
        ui.button('Full', on_click=lambda: set_mode('full')).props('size=sm color=primary')
        ui.button('Stretch', on_click=lambda: set_mode('stretch')).props('size=sm color=primary')

ui.run()