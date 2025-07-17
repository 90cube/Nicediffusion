"""
이미지-이미지 생성 모드 도메인 로직
UI나 Services에 의존하지 않는 순수한 비즈니스 로직
"""

import torch
import asyncio
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from PIL import Image


@dataclass
class Img2ImgParams:
    """이미지-이미지 생성 파라미터 (A1111 스타일)"""
    prompt: str
    negative_prompt: str
    init_image: Image.Image
    strength: float  # 0.0 ~ 1.0 (0.0: 원본 유지, 1.0: 완전히 새로 생성)
    width: int
    height: int
    steps: int
    cfg_scale: float
    seed: int
    sampler: str
    scheduler: str
    batch_size: int
    model_type: str = 'SD15'
    clip_skip: int = 1  # CLIP Skip 추가
    size_match_enabled: bool = False  # 크기 일치 모드 추가
    
    # A1111 추가 파라미터들
    image_cfg_scale: float = 10  # 이미지 CFG 스케일 (A1111 image_cfg_scale)
    resize_mode: int = 0  # 리사이즈 모드 (0st resize, 1: Crop and resize, 2 Resize and fill)
    mask_blur: int = 4 # 마스크 블러 (인페인팅용)
    inpainting_fill: int = 1  # 인페인팅 채우기 모드 (0: fill, 1: original, 2: latent noise,3: latent nothing)
    inpaint_full_res: bool = False  # 전체 해상도 인페인팅
    inpaint_full_res_padding: int = 32# 전체 해상도 패딩
    inpainting_mask_invert: int = 0  # 마스크 반전 (0: normal, 1: invert)
    eta: float = 1.0 # ETA (노이즈 스케줄링)
    tiling: bool = False  # 타일링 모드
    restore_faces: bool = False  # 얼굴 복원
    subseed: int = -1# 서브시드
    subseed_strength: float = 0# 서브시드 강도
    seed_resize_from_h: int =-1  # 시드 리사이즈 높이
    seed_resize_from_w: int =-1  # 시드 리사이즈 너비
    sampler_index: int = 0  # 샘플러 인덱스
    script_name: str = ""  # 스크립트 이름
    script_args: list = field(default_factory=list)  # 스크립트 인수
    send_images: bool = True  # 이미지 전송
    save_images: bool = False  # 이미지 저장
    alwayson_scripts: dict = field(default_factory=dict)  # 항상 실행 스크립트


class Img2ImgMode:
    """이미지-이미지 생성 모드 (A1111 스타일)"""
    
    def __init__(self, pipeline: Any, device: str):
        self.pipeline = pipeline
        self.device = device
    
    def _encode_image(self, input_image: Image.Image) -> torch.Tensor:
        """이미지를 latent space로 인코딩 (상세 디버깅 버전)"""
        import torch
        import numpy as np
        
        print("=" * 80)
        print("🔍 [DEBUG] 이미지 → Latent 변환 과정 상세 분석")
        print("=" * 80)
        
        # 1단계: 입력 이미지 검증
        print(f"📥 1단계: 입력 이미지 검증")
        print(f"   - 이미지 타입: {type(input_image)}")
        print(f"   - 이미지 크기: {input_image.size}")
        print(f"   - 이미지 모드: {input_image.mode}")
        print(f"   - 이미지 포맷: {getattr(input_image, 'format', 'Unknown')}")
        
        if input_image is None:
            raise ValueError("❌ 입력 이미지가 None입니다!")
        
        # 2단계: RGB 변환
        print(f"\n🔄 2단계: RGB 변환")
        original_mode = input_image.mode
        if input_image.mode != 'RGB':
            print(f"   - 원본 모드: {original_mode} → RGB로 변환")
            input_image = input_image.convert('RGB')
        else:
            print(f"   - 이미 RGB 모드입니다")
        
        print(f"   - 변환 후 모드: {input_image.mode}")
        
        # 3단계: 이미지 전처리
        print(f"\n⚙️ 3단계: 이미지 전처리")
        
        with torch.no_grad():
            try:
                # 방법 1: image_processor 사용 (SDXL)
                if hasattr(self.pipeline, 'image_processor') and self.pipeline.image_processor is not None:
                    print(f"   - 방법 1: image_processor 사용")
                    print(f"   - image_processor 타입: {type(self.pipeline.image_processor)}")
                    
                    image_tensor = self.pipeline.image_processor.preprocess(input_image)
                    print(f"   ✅ image_processor 전처리 성공")
                    
                # 방법 2: feature_extractor 사용 (SD15)
                elif hasattr(self.pipeline, 'feature_extractor') and self.pipeline.feature_extractor is not None:
                    print(f"   - 방법 2: feature_extractor 사용")
                    print(f"   - feature_extractor 타입: {type(self.pipeline.feature_extractor)}")
                    
                    result = self.pipeline.feature_extractor(input_image, return_tensors="pt")
                    image_tensor = result.pixel_values
                    print(f"   ✅ feature_extractor 전처리 성공")
                    
                # 방법 3: 수동 전처리 (fallback)
                else:
                    print(f"   - 방법 3: 수동 전처리 (torchvision transforms)")
                    import torchvision.transforms as transforms
                    
                    transform = transforms.Compose([
                        transforms.ToTensor(),
                        transforms.Normalize([0.5, 0.5, 0.5], [0.5, 0.5, 0.5])  # -1 to 1로 정규화
                    ])
                    image_tensor = transform(input_image).unsqueeze(0)
                    print(f"   ✅ 수동 전처리 성공")
                    
            except Exception as e:
                print(f"   ❌ 전처리 방법 1-3 실패: {e}")
                print(f"   - 최후의 수단: numpy 직접 변환")
                
                # 최후의 수단: 직접 변환
                np_image = np.array(input_image).astype(np.float32) / 255.0
                np_image = (np_image - 0.5) / 0.5  # -1 to 1
                image_tensor = torch.from_numpy(np_image).permute(2, 0, 1).unsqueeze(0)
                print(f"   ✅ numpy 직접 변환 성공")
            
            # 4단계: 전처리 결과 검증
            print(f"\n🔍 4단계: 전처리 결과 검증")
            print(f"   - tensor shape: {image_tensor.shape}")
            print(f"   - tensor dtype: {image_tensor.dtype}")
            print(f"   - tensor device: {image_tensor.device}")
            print(f"   - 값의 범위: [{image_tensor.min().item():.3f}, {image_tensor.max().item():.3f}]")
            print(f"   - 평균값: {image_tensor.mean().item():.3f}")
            print(f"   - 표준편차: {image_tensor.std().item():.3f}")
            
            # 값 범위 검증
            if image_tensor.min() < -1.1 or image_tensor.max() > 1.1:
                print(f"   ⚠️ 경고: 값 범위가 예상 범위 [-1, 1]을 벗어남!")
            
            # 5단계: 디바이스 및 데이터 타입 변환
            print(f"\n🔄 5단계: 디바이스 및 데이터 타입 변환")
            print(f"   - 대상 디바이스: {self.device}")
            print(f"   - VAE dtype: {self.pipeline.vae.dtype}")
            
            image_tensor = image_tensor.to(self.device, dtype=self.pipeline.vae.dtype)
            print(f"   - 변환 후 device: {image_tensor.device}")
            print(f"   - 변환 후 dtype: {image_tensor.dtype}")
            
            # 6단계: VAE 인코딩
            print(f"\n🎨 6단계: VAE 인코딩")
            print(f"   - VAE 타입: {type(self.pipeline.vae)}")
            print(f"   - VAE config: {self.pipeline.vae.config}")
            
            try:
                # VAE 인코딩
                vae_output = self.pipeline.vae.encode(image_tensor)
                print(f"   ✅ VAE 인코딩 성공")
                print(f"   - VAE 출력 타입: {type(vae_output)}")
                
                # latent_dist에서 샘플링
                if hasattr(vae_output, 'latent_dist'):
                    print(f"   - latent_dist 존재: {type(vae_output.latent_dist)}")
                    latent = vae_output.latent_dist.sample()
                    print(f"   ✅ latent_dist.sample() 성공")
                else:
                    print(f"   - latent_dist 없음, 직접 사용")
                    latent = vae_output
                
                print(f"   - 샘플링 후 latent shape: {latent.shape}")
                print(f"   - 샘플링 후 latent dtype: {latent.dtype}")
                print(f"   - 샘플링 후 값 범위: [{latent.min().item():.3f}, {latent.max().item():.3f}]")
                
            except Exception as e:
                print(f"   ❌ VAE 인코딩 실패: {e}")
                import traceback
                traceback.print_exc()
                raise
            
            # 7단계: 스케일링 팩터 적용
            print(f"\n📏 7단계: 스케일링 팩터 적용")
            scaling_factor = self.pipeline.vae.config.scaling_factor
            print(f"   - VAE scaling_factor: {scaling_factor}")
            
            latent = latent * scaling_factor
            print(f"   - 스케일링 후 latent shape: {latent.shape}")
            print(f"   - 스케일링 후 latent dtype: {latent.dtype}")
            print(f"   - 스케일링 후 값 범위: [{latent.min().item():.3f}, {latent.max().item():.3f}]")
            
            # 8단계: 최종 검증
            print(f"\n✅ 8단계: 최종 검증")
            print(f"   - 최종 latent shape: {latent.shape}")
            print(f"   - 최종 latent dtype: {latent.dtype}")
            print(f"   - 최종 latent device: {latent.device}")
            print(f"   - 최종 값 범위: [{latent.min().item():.3f}, {latent.max().item():.3f}]")
            
            # 예상 shape 검증
            expected_channels = 4  # VAE latent channels
            expected_height = image_tensor.shape[2] * 8  # VAE downsampling factor
            expected_width = image_tensor.shape[3] * 8   # VAE downsampling factor
            
            print(f"   - 예상 shape: [1, {expected_channels}, {expected_height}, {expected_width}]")
            print(f"   - 실제 shape: {list(latent.shape)}")
            
            if latent.shape[1] != expected_channels:
                print(f"   ⚠️ 경고: 채널 수가 예상과 다름!")
            if latent.shape[2] != expected_height or latent.shape[3] != expected_width:
                print(f"   ⚠️ 경고: 공간 차원이 예상과 다름!")
            
            print("=" * 80)
            print("🎉 이미지 → Latent 변환 완료!")
            print("=" * 80)
            
            return latent
    
    def _validate_init_image(self, init_image: Image.Image, target_width: int, target_height: int, size_match_enabled: bool = False) -> Image.Image:
        """초기 이미지 검증 및 리사이즈"""
        if init_image is None:
            raise ValueError("초기 이미지가 필요합니다.")
        
        # size_match_enabled가 활성화되어 있으면 원본 크기 유지
        if size_match_enabled:
            print(f"✅ 크기 일치 모드: 원본 이미지 크기 유지 {init_image.size}")
            return init_image
        
        # 이미지 크기 조정
        if init_image.size != (target_width, target_height):
            print(f"🔄 초기 이미지 크기 조정: {init_image.size} -> ({target_width}, {target_height})")
            init_image = init_image.resize((target_width, target_height), Image.Resampling.LANCZOS)
        
        return init_image
    
    def _validate_strength(self, strength: float) -> float:
        """강도 값 검증"""
        if strength < 0.0 or strength > 1.0:
            raise ValueError("강도 값은 0.0 ~ 1.0 사이여야 합니다.")
        return strength
    
    def _apply_sd15_optimizations(self, params: Img2ImgParams):
        """SD15 모델 최적화 설정 적용"""
        if params.model_type != 'SD15':
            return
            
        # SD15에서 더 정확한 결과를 위한 설정
        if hasattr(self.pipeline.scheduler, 'config'):
            self.pipeline.scheduler.config.use_karras_sigmas = True
            self.pipeline.scheduler.config.karras_rho = 7.0
        
        # SD15에서 더 나은 노이즈 스케줄링
        if hasattr(self.pipeline.scheduler, 'set_timesteps'):
            self.pipeline.scheduler.set_timesteps(params.steps, device=self.device)
        
        # SD15에서 더 안정적인 생성
        if hasattr(self.pipeline.scheduler, 'beta_start'):
            self.pipeline.scheduler.beta_start = 0.00085
        if hasattr(self.pipeline.scheduler, 'beta_end'):
            self.pipeline.scheduler.beta_end = 0.012
        
        # SD15에서 더 선명한 결과를 위한 설정
        if hasattr(self.pipeline, 'enable_attention_slicing'):
            self.pipeline.enable_attention_slicing(1)
        if hasattr(self.pipeline, 'enable_vae_slicing'):
            self.pipeline.enable_vae_slicing()
        
        # xformers는 선택적 기능이므로 안전하게 처리
        try:
            if hasattr(self.pipeline, 'enable_xformers_memory_efficient_attention'):
                self.pipeline.enable_xformers_memory_efficient_attention()
        except ModuleNotFoundError:
            pass  # 조용히 무시
    
    async def generate(self, params: Img2ImgParams) -> List[Any]:
        """이미지-이미지 생성 실행 (Strength 값 상세 검증)"""
        import torch
        import numpy as np
        from PIL import Image
        from skimage.metrics import structural_similarity as ssim
        from skimage.metrics import mean_squared_error as mse
        
        print("=" * 100)
        print("🔍 [STRENGTH 검증] Img2Img Strength 값 상세 분석")
        print("=" * 100)
        
        # 1. StateManager에서 가져온 strength 값 확인
        print(f"📊 1단계: StateManager에서 가져온 strength 값")
        print(f"   - params.strength: {params.strength}")
        print(f"   - 타입: {type(params.strength)}")
        print(f"   - 범위 검증: {0.0 <= params.strength <= 1.0}")
        
        # 파라미터 검증
        size_match_enabled = getattr(params, 'size_match_enabled', False)
        init_image = self._validate_init_image(params.init_image, params.width, params.height, size_match_enabled)
        strength = self._validate_strength(params.strength)
        
        print(f"   - 검증 후 strength: {strength}")
        print(f"   - 원본 이미지 크기: {init_image.size}")
        print(f"   - 목표 크기: {params.width}x{params.height}")
        
        # 생성기 설정
        generator = torch.Generator(device=self.device)
        if params.seed > 0:
            generator.manual_seed(params.seed)
            print(f"   - 시드 설정: {params.seed}")
        else:
            print(f"   - 랜덤 시드 사용")
        
        def _generate_with_strength_validation():
            """Strength 값 검증을 포함한 생성 로직"""
            print(f"\n🔍 2단계: 파이프라인 호출 시 전달되는 실제 strength 값")
            
            # 스케줄러 timesteps 설정 및 검증
            if hasattr(self.pipeline.scheduler, 'set_timesteps'):
                self.pipeline.scheduler.set_timesteps(params.steps, device=self.device)
                print(f"   - 스케줄러 timesteps 설정: {params.steps}")
                
                # 3. 노이즈 스케줄러의 timestep 계산 검증
                print(f"\n🔍 3단계: 노이즈 스케줄러의 timestep 계산")
                if hasattr(self.pipeline.scheduler, 'timesteps'):
                    timesteps = self.pipeline.scheduler.timesteps
                    print(f"   - 전체 timesteps: {len(timesteps)}")
                    print(f"   - 첫 번째 timestep: {timesteps[0].item()}")
                    print(f"   - 마지막 timestep: {timesteps[-1].item()}")
                    
                    # Strength에 따른 시작 timestep 계산
                    start_timestep_idx = int((1.0 - strength) * len(timesteps))
                    start_timestep = timesteps[start_timestep_idx] if start_timestep_idx < len(timesteps) else timesteps[0]
                    
                    print(f"   - Strength {strength} → 시작 timestep 인덱스: {start_timestep_idx}")
                    print(f"   - 시작 timestep 값: {start_timestep.item()}")
                    print(f"   - 건너뛸 timesteps: {start_timestep_idx}개")
                    print(f"   - 실제 실행 timesteps: {len(timesteps) - start_timestep_idx}개")
            
            # 4. init_image latent와 노이즈 적용된 latent 비교
            print(f"\n🔍 4단계: init_image latent 분석")
            init_latent = self._encode_image(init_image)
            print(f"   - 원본 이미지 latent shape: {init_latent.shape}")
            print(f"   - 원본 이미지 latent 범위: [{init_latent.min().item():.3f}, {init_latent.max().item():.3f}]")
            print(f"   - 원본 이미지 latent 평균: {init_latent.mean().item():.3f}")
            print(f"   - 원본 이미지 latent 표준편차: {init_latent.std().item():.3f}")
            
            # 파이프라인 호출 전 파라미터 검증
            print(f"\n🔍 2단계: 파이프라인 호출 시 전달되는 실제 strength 값")
            print(f"   - 전달할 strength: {strength}")
            print(f"   - 전달할 steps: {params.steps}")
            print(f"   - 전달할 cfg_scale: {params.cfg_scale}")
            print(f"   - 전달할 이미지 크기: {init_image.size}")
            
            # 파이프라인 호출
            try:
                result = self.pipeline(
                    prompt=params.prompt,
                    negative_prompt=params.negative_prompt,
                    image=init_image,
                    strength=strength,
                    width=params.width,
                    height=params.height,
                    num_inference_steps=params.steps,
                    guidance_scale=params.cfg_scale,
                    generator=generator,
                    num_images_per_prompt=params.batch_size
                )
                
                print(f"   ✅ 파이프라인 호출 성공")
                
            except Exception as e:
                print(f"   ❌ 파이프라인 호출 실패: {e}")
                import traceback
                traceback.print_exc()
                return []
            
            # 결과 이미지 반환
            if hasattr(result, 'images'):
                return result.images
            else:
                return result if isinstance(result, list) else [result]
        
        # 생성 실행
        generated_images = await asyncio.to_thread(_generate_with_strength_validation)
        
        if not generated_images:
            print(f"❌ 이미지 생성 실패")
            return []
        
        print(f"\n🔍 5단계: 결과 이미지와 원본 이미지의 유사도 측정")
        
        # 결과 이미지 분석
        result_image = generated_images[0]
        print(f"   - 생성된 이미지 크기: {result_image.size}")
        print(f"   - 생성된 이미지 모드: {result_image.mode}")
        
        # 이미지 크기 통일 (비교를 위해)
        if result_image.size != init_image.size:
            print(f"   - 크기 통일을 위해 리사이즈: {result_image.size} → {init_image.size}")
            result_image = result_image.resize(init_image.size, Image.Resampling.LANCZOS)
        
        # 이미지를 numpy 배열로 변환
        init_array = np.array(init_image.convert('RGB'))
        result_array = np.array(result_image.convert('RGB'))
        
        # 정규화 (0-255 → 0-1)
        init_array_norm = init_array.astype(np.float32) / 255.0
        result_array_norm = result_array.astype(np.float32) / 255.0
        
        # SSIM 계산 (이미지 크기 검증 후)
        try:
            # 이미지 크기가 SSIM 계산에 충분한지 확인
            min_size = 7  # SSIM의 최소 윈도우 크기
            if init_array_norm.shape[0] < min_size or init_array_norm.shape[1] < min_size:
                print(f"   - 이미지가 너무 작아 SSIM 계산 불가: {init_array_norm.shape}")
                ssim_score = None
            else:
                # 윈도우 크기를 이미지 크기에 맞게 조정
                win_size = min(7, min(init_array_norm.shape[0], init_array_norm.shape[1]))
                if win_size % 2 == 0:  # 짝수인 경우 홀수로 조정
                    win_size -= 1
                
                ssim_score = ssim(init_array_norm, result_array_norm, 
                                 multichannel=True, data_range=1.0, 
                                 win_size=win_size)
                print(f"   - SSIM 유사도: {ssim_score:.4f} (win_size={win_size})")
        except Exception as e:
            print(f"   - SSIM 계산 실패: {e}")
            ssim_score = None
        
        # MSE 계산
        try:
            mse_score = mse(init_array_norm, result_array_norm)
            print(f"   - MSE 오차: {mse_score:.6f}")
        except Exception as e:
            print(f"   - MSE 계산 실패: {e}")
            mse_score = None
        
        # 예상 유사도와 비교
        print(f"\n📊 Strength {strength} 예상 vs 실제 유사도 비교:")
        if strength == 0.3:
            expected_ssim = 0.7
            print(f"   - 예상 SSIM: {expected_ssim} (원본과 70% 유사)")
        elif strength == 0.8:
            expected_ssim = 0.2
            print(f"   - 예상 SSIM: {expected_ssim} (원본과 20% 유사)")
        else:
            expected_ssim = 1.0 - strength
            print(f"   - 예상 SSIM: {expected_ssim:.3f} (1 - strength)")
        
        if ssim_score is not None:
            print(f"   - 실제 SSIM: {ssim_score:.4f}")
            difference = abs(ssim_score - expected_ssim)
            print(f"   - 차이: {difference:.4f}")
            
            if difference < 0.1:
                print(f"   ✅ Strength가 정상적으로 작동함 (차이 < 0.1)")
            elif difference < 0.2:
                print(f"   ⚠️ Strength가 부분적으로 작동함 (차이 < 0.2)")
            else:
                print(f"   ❌ Strength가 제대로 작동하지 않음 (차이 >= 0.2)")
        
        print("=" * 100)
        print("🎉 Strength 검증 완료")
        print("=" * 100)
        
        return generated_images
    
    async def upscale(self, image: Image.Image, scale_factor: float = 2.0) -> Image.Image:
        """이미지 업스케일 (간단한 구현)"""
        if scale_factor <= 1.0:
            return image
        
        new_width = int(image.width * scale_factor)
        new_height = int(image.height * scale_factor)
        
        print(f"🔄 업스케일: {image.size} -> ({new_width}, {new_height})")
        
        # 고품질 리사이즈
        upscaled_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        return upscaled_image
    
    async def inpaint(self, image: Image.Image, mask: Image.Image, prompt: str, 
                     negative_prompt: str = "", strength: float = 0.8) -> List[Any]:
        """인페인팅 (마스크 기반 이미지 수정)"""
        print(f"🎨 인페인팅 시작 - Strength: {strength}")
        
        # 마스크 검증
        if mask.size != image.size:
            print(f"🔄 마스크 크기 조정: {mask.size} -> {image.size}")
            mask = mask.resize(image.size, Image.Resampling.LANCZOS)
        
        # 생성기 설정
        generator = torch.Generator(device=self.device)
        generator.manual_seed(int(torch.randint(0, 2**32 - 1, (1,)).item()))
        
        def _inpaint():
            """인페인팅 생성 로직"""
            # 인페인팅 파이프라인 호출 (파이프라인이 지원하는 경우)
            if hasattr(self.pipeline, 'inpaint'):
                result = self.pipeline.inpaint(
                    prompt=prompt,
                    negative_prompt=negative_prompt,
                    image=image,
                    mask_image=mask,
                    strength=strength,
                    generator=generator,
                    num_inference_steps=20,
                    guidance_scale=7.0
                )
                return result.images if hasattr(result, 'images') else [result]
            else:
                # 인페인팅을 지원하지 않는 경우 일반 img2img로 대체
                print("⚠️ 인페인팅을 지원하지 않는 파이프라인입니다. 일반 img2img로 대체합니다.")
                return self.pipeline(
                    prompt=prompt,
                    negative_prompt=negative_prompt,
                    image=image,
                    strength=strength,
                    generator=generator,
                    num_inference_steps=20,
                    guidance_scale=7.0
                ).images
        
        # 별도 스레드에서 생성 수행
        generated_images = await asyncio.to_thread(_inpaint)
        
        print(f"✅ 인페인팅 완료: {len(generated_images)}개 이미지")
        return generated_images
