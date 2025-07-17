# img2img.py의 generate 메서드 수정

async def generate(self, params: Img2ImgParams) -> List[Any]:
    """이미지-이미지 생성 실행 (올바른 denoising 구현)"""
    print(f"🎨 Img2Img 생성 시작 - Seed: {params.seed}, Strength: {params.strength}")
    print(f"🔧 Steps: {params.steps}, Denoising Steps: {int(params.steps * params.strength)}")
    
    if params.init_image is None:
        print("❌ 초기 이미지가 없습니다!")
        return []
    
    # 파라미터 검증
    init_image = self._validate_init_image(params.init_image, params.width, params.height)
    strength = self._validate_strength(params.strength)
    
    # 스케줄러 설정
    from ..scheduler_manager import SchedulerManager
    SchedulerManager.apply_scheduler_to_pipeline(
        self.pipeline, 
        params.sampler, 
        params.scheduler
    )
    
    # 생성기 설정
    generator = torch.Generator(device=self.device)
    if params.seed > 0:
        generator.manual_seed(params.seed)
    
    def _generate():
        """실제 생성 로직 (올바른 A1111 스타일)"""
        
        # 방법 1: StableDiffusionImg2ImgPipeline을 사용하는 경우
        if hasattr(self.pipeline, '__class__') and 'Img2Img' in self.pipeline.__class__.__name__:
            # 전용 img2img 파이프라인
            print("✅ 전용 Img2Img 파이프라인 사용")
            result = self.pipeline(
                prompt=params.prompt,
                negative_prompt=params.negative_prompt,
                image=init_image,
                strength=strength,  # 파이프라인이 내부적으로 처리
                num_inference_steps=params.steps,
                guidance_scale=params.cfg_scale,
                generator=generator,
                num_images_per_prompt=params.batch_size,
            )
            return result.images
        
        # 방법 2: 일반 StableDiffusionPipeline을 img2img로 사용
        print("⚠️ 일반 파이프라인으로 img2img 구현")
        
        # 1. 이미지를 latent로 인코딩
        init_latent = self._encode_image(init_image)
        
        # 2. 스케줄러의 timesteps 설정
        self.pipeline.scheduler.set_timesteps(params.steps, device=self.device)
        timesteps = self.pipeline.scheduler.timesteps
        
        # 3. strength에 따른 시작 timestep 계산 (중요!)
        # strength = 1.0: 모든 스텝 실행 (완전 재생성)
        # strength = 0.0: 스텝 실행 안함 (원본 유지)
        init_timestep = int(params.steps * (1 - strength))
        init_timestep = min(init_timestep, params.steps - 1)
        
        # 실제 사용할 timesteps
        timesteps = timesteps[init_timestep:]
        num_inference_steps = len(timesteps)
        
        print(f"📊 Denoising 정보:")
        print(f"  - 전체 스텝: {params.steps}")
        print(f"  - 시작 스텝: {init_timestep}")
        print(f"  - 실행 스텝: {num_inference_steps}")
        print(f"  - Strength: {strength}")
        
        # 4. 초기 노이즈 추가
        noise = torch.randn_like(init_latent, generator=generator)
        
        # 첫 번째 timestep에서 노이즈 추가
        if len(timesteps) > 0:
            init_latent = self.pipeline.scheduler.add_noise(
                init_latent, 
                noise, 
                timesteps[0]
            )
        
        # 5. 텍스트 임베딩 생성
        text_embeddings = self._get_text_embeddings(params.prompt, params.negative_prompt)
        
        # 6. Diffusion 루프 실행
        latents = init_latent
        
        for i, t in enumerate(timesteps):
            # CFG를 위한 latent 복제
            latent_model_input = torch.cat([latents] * 2)
            
            # 노이즈 예측
            with torch.no_grad():
                noise_pred = self.pipeline.unet(
                    latent_model_input,
                    t,
                    encoder_hidden_states=text_embeddings,
                ).sample
            
            # CFG 적용
            noise_pred_uncond, noise_pred_text = noise_pred.chunk(2)
            noise_pred = noise_pred_uncond + params.cfg_scale * (noise_pred_text - noise_pred_uncond)
            
            # 스케줄러 스텝
            latents = self.pipeline.scheduler.step(noise_pred, t, latents).prev_sample
            
            # 진행률 표시 (선택사항)
            if i % 5 == 0:
                print(f"  스텝 {i+1}/{num_inference_steps} 완료...")
        
        # 7. latent를 이미지로 디코딩
        with torch.no_grad():
            latents = 1 / self.pipeline.vae.config.scaling_factor * latents
            image = self.pipeline.vae.decode(latents).sample
            
        # 8. 후처리
        image = (image / 2 + 0.5).clamp(0, 1)
        image = image.cpu().permute(0, 2, 3, 1).float().numpy()
        
        # PIL 이미지로 변환
        if image.shape[0] == 1:
            image = image[0]
            image = Image.fromarray((image * 255).astype('uint8'))
            return [image]
        else:
            images = []
            for i in range(image.shape[0]):
                img = Image.fromarray((image[i] * 255).astype('uint8'))
                images.append(img)
            return images
    
    def _get_text_embeddings(self, prompt: str, negative_prompt: str):
        """텍스트 임베딩 생성"""
        # 프롬프트 토큰화
        text_input = self.pipeline.tokenizer(
            [prompt],
            padding="max_length",
            max_length=self.pipeline.tokenizer.model_max_length,
            truncation=True,
            return_tensors="pt",
        )
        
        # 네거티브 프롬프트 토큰화
        uncond_input = self.pipeline.tokenizer(
            [negative_prompt],
            padding="max_length",
            max_length=self.pipeline.tokenizer.model_max_length,
            truncation=True,
            return_tensors="pt",
        )
        
        # 임베딩 생성
        with torch.no_grad():
            text_embeddings = self.pipeline.text_encoder(
                text_input.input_ids.to(self.device)
            )[0]
            uncond_embeddings = self.pipeline.text_encoder(
                uncond_input.input_ids.to(self.device)
            )[0]
        
        # CFG를 위해 concat
        text_embeddings = torch.cat([uncond_embeddings, text_embeddings])
        return text_embeddings
    
    # 별도 스레드에서 생성 수행
    generated_images = await asyncio.to_thread(_generate)
    
    print(f"✅ Img2Img 완료: {len(generated_images)}개 이미지")
    return generated_images