# state_manager.py의 start_generation 메서드 수정

async def start_generation(self):
    """이미지 생성 시작 (수정된 버전)"""
    if self.get('is_generating'):
        self._notify_user('이미 생성 중입니다.', 'warning')
        return
    
    if not self.model_loader.get_current_pipeline():
        self._notify_user('모델을 먼저 로드해주세요.', 'warning')
        return
    
    self.stop_generation_flag.clear()
    self.set('is_generating', True)
    
    try:
        # 도메인 전략 사용
        pipeline = self.model_loader.get_current_pipeline()
        strategy = BasicGenerationStrategy(pipeline, self.device, state=self)
        
        # 파라미터 준비
        params = self.get('current_params')
        params_dict = {
            'prompt': params.prompt,
            'negative_prompt': params.negative_prompt,
            'width': params.width,
            'height': params.height,
            'steps': params.steps,
            'cfg_scale': params.cfg_scale,
            'seed': params.seed,
            'sampler': params.sampler,
            'scheduler': params.scheduler,
            'batch_size': params.batch_size,
            'clip_skip': getattr(params, 'clip_skip', 1),
            'vae': self.get('current_vae_path'),
            'loras': self.get('current_loras')
        }
        
        # 현재 모드 확인
        current_mode = self.get('current_mode', 'txt2img')
        
        # i2i 모드 처리
        if current_mode in ['img2img', 'inpaint', 'upscale']:
            params_dict['img2img_mode'] = True
            
            # strength 값 추가 (중요!)
            strength = getattr(params, 'strength', 0.8)
            params_dict['strength'] = strength
            print(f"🔧 i2i Strength 값: {strength}")
            
            # init_image 추가 (중요!)
            init_image = self.get('init_image')
            if init_image is None:
                # uploaded_image에서 가져오기 시도
                uploaded_image = self.get('uploaded_image')
                if uploaded_image is not None:
                    # numpy to PIL
                    from PIL import Image
                    import numpy as np
                    if isinstance(uploaded_image, np.ndarray):
                        init_image = Image.fromarray(uploaded_image.astype('uint8'))
                        self.set('init_image', init_image)  # 저장
                    
            params_dict['init_image'] = init_image
            
            # 디버그 출력
            print(f"🔍 i2i 모드 파라미터:")
            print(f"  - init_image: {init_image}")
            print(f"  - strength: {strength}")
            print(f"  - size: {params.width}x{params.height}")
            
            if init_image is None:
                self._notify_user('이미지를 먼저 업로드해주세요.', 'warning')
                self.set('is_generating', False)
                return
        
        # 모델 정보
        model_info = self.get('current_model_info', {})
        
        # 생성 시작 이벤트
        self._notify('generation_started', {
            'mode': current_mode,
            'params': params_dict
        })
        
        # 전략 실행
        result = await strategy.execute(params_dict, model_info)
        
        if result.success and result.images:
            # 결과 처리
            self.set('last_generated_images', result.images)
            self._notify('image_generated', result.images)
            
            # 후처리
            await self._post_process_generation(result.images, params_dict)
            
            self._notify_user(f'{len(result.images)}개 이미지 생성 완료!', 'positive')
        else:
            error_msg = ', '.join(result.errors) if result.errors else '알 수 없는 오류'
            self._notify_user(f'생성 실패: {error_msg}', 'negative')
            
    except Exception as e:
        print(f"❌ 생성 중 오류: {e}")
        import traceback
        traceback.print_exc()
        self._notify_user(f'생성 중 오류 발생: {str(e)}', 'negative')
        
    finally:
        self.set('is_generating', False)
        self._notify('generation_completed', {})

# img2img.py의 _encode_image 메서드 개선

def _encode_image(self, image: Image.Image) -> torch.Tensor:
    """이미지를 latent space로 인코딩 (개선된 버전)"""
    print(f"🔍 이미지 인코딩 시작: 크기={image.size}, 모드={image.mode}")
    
    # RGB로 변환 (필수)
    if image.mode != 'RGB':
        image = image.convert('RGB')
    
    with torch.no_grad():
        # 이미지 전처리 - 더 안전한 방식
        try:
            # 방법 1: image_processor 사용
            if hasattr(self.pipeline, 'image_processor') and self.pipeline.image_processor is not None:
                image_tensor = self.pipeline.image_processor.preprocess(image)
            # 방법 2: feature_extractor 사용
            elif hasattr(self.pipeline, 'feature_extractor') and self.pipeline.feature_extractor is not None:
                image_tensor = self.pipeline.feature_extractor(
                    image, 
                    return_tensors="pt"
                ).pixel_values
            # 방법 3: 수동 전처리
            else:
                import torchvision.transforms as transforms
                transform = transforms.Compose([
                    transforms.ToTensor(),
                    transforms.Normalize([0.5], [0.5])  # -1 to 1로 정규화
                ])
                image_tensor = transform(image).unsqueeze(0)
                
        except Exception as e:
            print(f"⚠️ 이미지 전처리 중 오류, 수동 처리로 대체: {e}")
            # 최후의 수단: 직접 변환
            import numpy as np
            import torch
            np_image = np.array(image).astype(np.float32) / 255.0
            np_image = (np_image - 0.5) / 0.5  # -1 to 1
            image_tensor = torch.from_numpy(np_image).permute(2, 0, 1).unsqueeze(0)
        
        # 디바이스와 데이터 타입 맞추기
        image_tensor = image_tensor.to(self.device, dtype=self.pipeline.vae.dtype)
        
        # VAE 인코딩
        latent = self.pipeline.vae.encode(image_tensor).latent_dist.sample()
        latent = latent * self.pipeline.vae.config.scaling_factor
        
        print(f"✅ 이미지 인코딩 완료: latent shape={latent.shape}, dtype={latent.dtype}")
        return latent

# parameter_panel.py에 strength 슬라이더 추가 확인

def render_i2i_controls(self):
    """i2i 모드 전용 컨트롤 렌더링"""
    current_params = self.state.get('current_params')
    
    with ui.card().classes('w-full bg-gray-800 p-3'):
        ui.label('🎨 Image to Image 설정').classes('text-lg font-bold mb-2')
        
        # Strength 슬라이더 (중요!)
        strength_value = getattr(current_params, 'strength', 0.8)
        with ui.row().classes('w-full items-center gap-2'):
            ui.label('Strength:').classes('text-sm')
            self.strength_slider = ui.slider(
                min=0.0, 
                max=1.0, 
                step=0.05,
                value=strength_value
            ).on('update:model-value', 
                 lambda e: self.state.update_param('strength', e.args)
            ).classes('flex-1')
            ui.label(f'{strength_value:.2f}').classes('text-sm w-12 text-right')
        
        # Strength 설명
        ui.label('0.0 = 원본 유지, 1.0 = 완전 재생성').classes('text-xs text-gray-400')
        
        # 이미지 정보 표시
        init_image = self.state.get('init_image')
        if init_image:
            with ui.row().classes('w-full mt-2 text-sm'):
                if hasattr(init_image, 'size'):
                    ui.label(f'📐 크기: {init_image.size[0]}x{init_image.size[1]}')
                ui.label(f'📷 모드: {getattr(init_image, "mode", "Unknown")}')

# 이미지 업로드 시 자동 모드 전환 확인 (main.py)

@app.post('/api/upload_image')
async def upload_image(file: UploadFile = File(...)):
    """이미지 업로드 API 엔드포인트 (개선)"""
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert('RGB')
        
        # 크기 조정
        width, height = image.size
        max_size = 1544
        if width > max_size or height > max_size:
            if width > height:
                new_width = max_size
                new_height = int(height * (max_size / width))
            else:
                new_height = max_size
                new_width = int(width * (max_size / height))
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # StateManager에 저장
        state_manager.set('init_image', image)  # PIL Image 저장
        state_manager.set('uploaded_image', np.array(image))  # numpy도 저장
        
        # 현재 모드가 txt2img면 자동으로 img2img로 전환
        current_mode = state_manager.get('current_mode', 'txt2img')
        if current_mode == 'txt2img':
            state_manager.set('current_mode', 'img2img')
            print("🔄 자동으로 img2img 모드로 전환")
        
        # base64 반환
        buf = io.BytesIO()
        image.save(buf, format='PNG')
        b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        
        return {
            'success': True,
            'shape': image.size,
            'base64': f'data:image/png;base64,{b64}',
            'filename': file.filename,
            'mode': state_manager.get('current_mode')
        }
        
    except Exception as e:
        print(f"❌ 이미지 업로드 실패: {e}")
        return {'success': False, 'error': str(e)}