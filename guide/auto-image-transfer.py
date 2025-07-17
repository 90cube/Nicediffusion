# state_manager.py에 추가할 메서드

def transfer_generated_to_init(self):
    """생성된 이미지를 init_image로 전달"""
    last_generated = self.get('last_generated_image')
    if last_generated is not None:
        self.set('init_image', last_generated)
        self.set('uploaded_image', np.array(last_generated))
        return True
    return False

# parameter_panel.py의 모드 변경 처리

async def _on_mode_button_click(self, mode: str):
    """모드 선택 버튼 클릭 처리"""
    print(f"🔄 모드 선택: {mode}")
    
    previous_mode = self.state.get('current_mode')
    
    # t2i -> i2i 전환 시 자동 이미지 전달
    if previous_mode == 'txt2img' and mode in ['img2img', 'inpaint']:
        if self.state.transfer_generated_to_init():
            ui.notify('생성된 이미지를 가져왔습니다', type='positive')
    
    # StateManager에 현재 모드 설정
    self.state.set('current_mode', mode)
    
    # 모드별 기본 설정
    if mode in ['img2img', 'inpaint', 'upscale']:
        current_params = self.state.get('current_params')
        if not hasattr(current_params, 'strength') or current_params.strength is None:
            self.state.update_param('strength', 0.8)
    
    # 파라미터 패널 새로고침
    self.render.refresh()

# main.py의 생성 완료 후 처리

async def handle_generation_complete(images):
    """생성 완료 후 처리"""
    if images and len(images) > 0:
        # 마지막 생성 이미지 저장
        state_manager.set('last_generated_image', images[0])
        state_manager.set('image_generated', images)
        
        # 히스토리에 추가
        state_manager.add_to_history({
            'images': images,
            'params': state_manager.get('current_params'),
            'timestamp': datetime.now()
        })