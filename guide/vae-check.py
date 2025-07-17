# model_loader.py에 VAE 체크 추가

def load_vae(self, vae_path: str):
    """VAE 로드 및 확인"""
    if not self.current_pipeline:
        print("❌ 파이프라인이 로드되지 않았습니다.")
        return False
    
    try:
        if vae_path == 'baked_in':
            print("✅ 내장 VAE 사용")
            return True
        
        # VAE 로드
        from diffusers import AutoencoderKL
        print(f"🔄 VAE 로딩: {vae_path}")
        
        vae = AutoencoderKL.from_pretrained(
            vae_path,
            torch_dtype=self.current_pipeline.dtype
        ).to(self.device)
        
        # 파이프라인에 VAE 설정
        self.current_pipeline.vae = vae
        
        # VAE 정보 출력
        print(f"✅ VAE 로드 완료:")
        print(f"  - 타입: {type(vae).__name__}")
        print(f"  - Scaling factor: {vae.config.scaling_factor}")
        print(f"  - Latent channels: {vae.config.latent_channels}")
        
        return True
        
    except Exception as e:
        print(f"❌ VAE 로드 실패: {e}")
        return False

# generation_service.py에서 VAE 확인

async def check_pipeline_components(self):
    """파이프라인 컴포넌트 상태 확인"""
    pipeline = self.model_loader.get_current_pipeline()
    if not pipeline:
        return {
            'status': 'error',
            'message': '파이프라인이 로드되지 않았습니다.'
        }
    
    components = {
        'unet': hasattr(pipeline, 'unet') and pipeline.unet is not None,
        'vae': hasattr(pipeline, 'vae') and pipeline.vae is not None,
        'text_encoder': hasattr(pipeline, 'text_encoder') and pipeline.text_encoder is not None,
        'tokenizer': hasattr(pipeline, 'tokenizer') and pipeline.tokenizer is not None,
        'scheduler': hasattr(pipeline, 'scheduler') and pipeline.scheduler is not None,
    }
    
    # VAE 상세 정보
    vae_info = {}
    if components['vae']:
        vae = pipeline.vae
        vae_info = {
            'type': type(vae).__name__,
            'scaling_factor': getattr(vae.config, 'scaling_factor', 'Unknown'),
            'latent_channels': getattr(vae.config, 'latent_channels', 'Unknown'),
            'dtype': str(vae.dtype) if hasattr(vae, 'dtype') else 'Unknown'
        }
    
    # 파이프라인 타입 확인
    pipeline_info = {
        'type': type(pipeline).__name__,
        'supports_img2img': hasattr(pipeline, '__call__') and 'image' in pipeline.__call__.__code__.co_varnames,
        'supports_latents': hasattr(pipeline, '__call__') and 'latents' in pipeline.__call__.__code__.co_varnames,
    }
    
    return {
        'status': 'ok',
        'components': components,
        'vae_info': vae_info,
        'pipeline_info': pipeline_info
    }

# 디버그용: 생성 전 컴포넌트 체크
async def pre_generation_check(self):
    """생성 전 시스템 상태 체크"""
    print("\n🔍 생성 전 시스템 체크:")
    
    # 1. 파이프라인 체크
    check_result = await self.check_pipeline_components()
    print(f"📋 파이프라인 상태: {check_result['status']}")
    
    if check_result['status'] == 'ok':
        print("✅ 컴포넌트 상태:")
        for comp, status in check_result['components'].items():
            print(f"  - {comp}: {'✓' if status else '✗'}")
        
        print("📊 VAE 정보:")
        for key, value in check_result['vae_info'].items():
            print(f"  - {key}: {value}")
        
        print("🔧 파이프라인 정보:")
        for key, value in check_result['pipeline_info'].items():
            print(f"  - {key}: {value}")
    
    # 2. 현재 모드 체크
    current_mode = self.state.get('current_mode', 'txt2img')
    print(f"\n🎨 현재 모드: {current_mode}")
    
    # 3. i2i 모드일 때 init_image 체크
    if current_mode in ['img2img', 'inpaint']:
        init_image = self.state.get('init_image')
        uploaded_image = self.state.get('uploaded_image')
        
        print("🖼️ 이미지 상태:")
        print(f"  - init_image: {init_image}")
        print(f"  - uploaded_image: {uploaded_image}")
        
        if init_image:
            if hasattr(init_image, 'size'):
                print(f"  - 크기: {init_image.size}")
                print(f"  - 모드: {init_image.mode}")
        
    # 4. 파라미터 체크
    params = self.state.get('current_params')
    if params:
        print("\n⚙️ 주요 파라미터:")
        print(f"  - Steps: {params.steps}")
        print(f"  - CFG: {params.cfg_scale}")
        print(f"  - Size: {params.width}x{params.height}")
        if hasattr(params, 'strength'):
            print(f"  - Strength: {params.strength}")
    
    return check_result