# AdvancedTextEncoder 수정 (SDXL 지원 추가)

def is_sdxl_model(self) -> bool:
    """SDXL 모델인지 확인"""
    return hasattr(self.pipeline, 'text_encoder_2')

def encode_prompt(self, prompt: str, negative_prompt: str = "") -> tuple:
    """프롬프트 인코딩 (SDXL 자동 감지)"""
    
    if self.is_sdxl_model():
        return self.encode_prompt_sdxl(prompt, negative_prompt)
    else:
        return self.encode_prompt_sd15(prompt, negative_prompt)

def encode_prompt_sdxl(self, prompt: str, negative_prompt: str = "") -> tuple:
    """SDXL 전용 인코딩 (pooled embeddings 포함)"""
    
    # 첫 번째 텍스트 인코더 (CLIP ViT-L/14)
    pos_tokenized_1 = self.tokenize_with_weights(prompt)
    pos_embeds_1 = self._encode_tokens_with_encoder(pos_tokenized_1, self.pipeline.text_encoder)
    
    # 두 번째 텍스트 인코더 (OpenCLIP ViT-bigG/14) 
    pos_tokenized_2 = self.tokenize_with_weights_encoder2(prompt)
    pos_embeds_2, pos_pooled = self._encode_tokens_with_encoder(pos_tokenized_2, self.pipeline.text_encoder_2, return_pooled=True)
    
    # 연결 (SDXL 방식)
    pos_embeds = torch.cat([pos_embeds_1, pos_embeds_2], dim=-1)
    
    # 부정 프롬프트도 동일하게 처리
    if negative_prompt:
        neg_tokenized_1 = self.tokenize_with_weights(negative_prompt)
        neg_embeds_1 = self._encode_tokens_with_encoder(neg_tokenized_1, self.pipeline.text_encoder)
        
        neg_tokenized_2 = self.tokenize_with_weights_encoder2(negative_prompt)
        neg_embeds_2, neg_pooled = self._encode_tokens_with_encoder(neg_tokenized_2, self.pipeline.text_encoder_2, return_pooled=True)
        
        neg_embeds = torch.cat([neg_embeds_1, neg_embeds_2], dim=-1)
    else:
        # 빈 프롬프트 처리
        neg_embeds = torch.zeros_like(pos_embeds)
        neg_pooled = torch.zeros_like(pos_pooled)
    
    return pos_embeds, neg_embeds, pos_pooled, neg_pooled

def encode_prompt_sd15(self, prompt: str, negative_prompt: str = "") -> tuple:
    """SD15 전용 인코딩 (기존 방식)"""
    pos_embeds, neg_embeds = self.encode_prompt_original(prompt, negative_prompt)
    return pos_embeds, neg_embeds, None, None  # pooled는 None

# txt2img.py 수정
async def generate(self, params: Txt2ImgParams) -> List[Any]:
    # 인코딩
    result = encoder.encode_prompt(params.prompt, params.negative_prompt)
    
    if len(result) == 4:  # SDXL
        prompt_embeds, negative_prompt_embeds, pooled_prompt_embeds, negative_pooled_prompt_embeds = result
        
        pipeline_params = {
            'prompt_embeds': prompt_embeds,
            'negative_prompt_embeds': negative_prompt_embeds,
            'pooled_prompt_embeds': pooled_prompt_embeds,
            'negative_pooled_prompt_embeds': negative_pooled_prompt_embeds,
            # ... 나머지 파라미터
        }
    else:  # SD15
        prompt_embeds, negative_prompt_embeds = result[:2]
        
        pipeline_params = {
            'prompt_embeds': prompt_embeds,
            'negative_prompt_embeds': negative_prompt_embeds,
            # ... 나머지 파라미터
        }
