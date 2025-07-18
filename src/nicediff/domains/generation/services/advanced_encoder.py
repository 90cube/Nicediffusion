"""
고급 텍스트 인코더 서비스
ComfyUI 스타일 고급 인코딩으로 77토큰 제한 완전 해제
"""

import torch
import numpy as np
import itertools
import re
from typing import List, Tuple, Dict, Any, Optional
from math import gcd


class AdvancedTextEncoder:
    """ComfyUI 스타일 고급 텍스트 인코딩"""
    
    def __init__(self, pipeline, weight_mode="A1111", use_custom_tokenizer=True):
        self.pipeline = pipeline
        self.weight_mode = weight_mode  # "A1111" 또는 "comfy++"
        self.use_custom_tokenizer = use_custom_tokenizer
        self.tokenizer = pipeline.tokenizer
        self.text_encoder = pipeline.text_encoder
        
    def parse_prompt_weights(self, text: str) -> List[Tuple[str, float, int]]:
        """A1111 스타일 가중치 파싱: (word:1.2), ((word)), [word]"""
        
        # 가중치 패턴 정의
        patterns = [
            (r'\(\((.*?)\)\)', 1.21),  # ((word)) = 1.21
            (r'\((.*?):([0-9\.]+)\)', None),  # (word:1.2)
            (r'\((.*?)\)', 1.1),  # (word) = 1.1
            (r'\[(.*?)\]', 0.909),  # [word] = 1/1.1
        ]
        
        tokens = []
        word_id = 1
        
        remaining_text = text
        while remaining_text:
            matched = False
            
            # 패턴 매칭 시도
            for pattern, default_weight in patterns:
                match = re.search(pattern, remaining_text)
                if match:
                    # 매칭 이전 텍스트 처리
                    before = remaining_text[:match.start()].strip()
                    if before:
                        for word in before.split():
                            tokens.append((word, 1.0, word_id))
                            word_id += 1
                    
                    # 가중치 적용된 부분 처리
                    if default_weight is None:  # (word:1.2) 형태
                        word, weight = match.groups()
                        weight = float(weight)
                    else:
                        word = match.group(1)
                        weight = default_weight
                    
                    for w in word.strip().split():
                        tokens.append((w, weight, word_id))
                        word_id += 1
                    
                    # 매칭된 부분 제거
                    remaining_text = remaining_text[match.end():].strip()
                    matched = True
                    break
            
            if not matched:
                # 패턴이 없으면 일반 단어로 처리
                words = remaining_text.split()
                if words:
                    for word in words:
                        tokens.append((word, 1.0, word_id))
                        word_id += 1
                break
        
        return tokens
    
    def tokenize_with_weights(self, text: str) -> Dict[str, List]:
        """텍스트를 토큰화하고 가중치 정보 포함"""
        
        if not self.use_custom_tokenizer:
            # 기본 토크나이저 사용
            tokens = self.tokenizer.encode(text, add_special_tokens=True)
            weights = [1.0] * len(tokens)
            word_ids = list(range(len(tokens)))
            return {'tokens': [tokens], 'weights': [weights], 'word_ids': [word_ids]}
        
        # 고급 가중치 파싱
        parsed = self.parse_prompt_weights(text)
        
        tokens = []
        weights = []
        word_ids = []
        
        for word, weight, word_id in parsed:
            # 단어를 토큰으로 변환
            word_tokens = self.tokenizer.encode(word, add_special_tokens=False)
            
            tokens.extend(word_tokens)
            weights.extend([weight] * len(word_tokens))
            word_ids.extend([word_id] * len(word_tokens))
        
        # 특수 토큰 추가
        tokens = [self.tokenizer.bos_token_id] + tokens + [self.tokenizer.eos_token_id]
        weights = [1.0] + weights + [1.0]
        word_ids = [0] + word_ids + [0]
        
        return {'tokens': [tokens], 'weights': [weights], 'word_ids': [word_ids]}
    
    def _grouper(self, n, iterable):
        """청킹 헬퍼"""
        it = iter(iterable)
        while True:
            chunk = list(itertools.islice(it, n))
            if not chunk:
                return
            yield chunk
    
    def _norm_mag(self, w, n):
        """가중치 정규화"""
        d = w - 1
        return 1 + np.sign(d) * np.sqrt(np.abs(d)**2 / n)
    
    def divide_length(self, word_ids, weights):
        """단어 길이별 가중치 분배"""
        sums = dict(zip(*np.unique(word_ids, return_counts=True)))
        sums[0] = 1
        weights = [[self._norm_mag(w, sums[id]) if id != 0 else 1.0
                    for w, id in zip(x, y)] for x, y in zip(weights, word_ids)]
        return weights
    
    def from_zero(self, weights, base_emb):
        """가중치를 임베딩에 적용 (A1111 방식)"""
        weight_tensor = torch.tensor(weights, dtype=base_emb.dtype, device=base_emb.device)
        weight_tensor = weight_tensor.reshape(1, -1, 1).expand(base_emb.shape)
        return base_emb * weight_tensor
    
    def encode_prompt(self, prompt: str, negative_prompt: str = "") -> Tuple[torch.Tensor, torch.Tensor]:
        """프롬프트 인코딩 (메인 함수)"""
        
        # 긍정 프롬프트 처리
        pos_tokenized = self.tokenize_with_weights(prompt)
        pos_embeddings = self._encode_tokens(pos_tokenized)
        
        # 부정 프롬프트 처리
        if negative_prompt:
            neg_tokenized = self.tokenize_with_weights(negative_prompt)
            neg_embeddings = self._encode_tokens(neg_tokenized)
        else:
            # 빈 프롬프트 임베딩
            empty_tokens = self.tokenizer.encode("", add_special_tokens=True)
            empty_input = torch.tensor([empty_tokens], device=self.text_encoder.device)
            with torch.no_grad():
                neg_embeddings = self.text_encoder(empty_input)[0]
        
        return pos_embeddings, neg_embeddings
    
    def _encode_tokens(self, tokenized_data: Dict[str, List]) -> torch.Tensor:
        """토큰을 임베딩으로 변환"""
        
        tokens = tokenized_data['tokens'][0]
        weights = tokenized_data['weights'][0]
        word_ids = tokenized_data['word_ids'][0]
        
        # 토큰 길이 조정 (77토큰 제한 해제)
        max_length = 77  # 기본값, 필요시 확장
        if len(tokens) > max_length:
            # 청킹 처리
            return self._encode_long_prompt(tokens, weights, word_ids, max_length)
        
        # 패딩
        while len(tokens) < max_length:
            tokens.append(self.tokenizer.pad_token_id or 0)
            weights.append(1.0)
            word_ids.append(0)
        
        # 기본 임베딩 생성
        token_tensor = torch.tensor([tokens], device=self.text_encoder.device)
        with torch.no_grad():
            base_embeddings = self.text_encoder(token_tensor)[0]
        
        # 가중치 적용
        if self.weight_mode == "A1111":
            return self._apply_a1111_weights(base_embeddings, weights, word_ids)
        elif self.weight_mode == "comfy++":
            return self._apply_comfy_weights(base_embeddings, weights, word_ids)
        else:
            return base_embeddings
    
    def _encode_long_prompt(self, tokens: List[int], weights: List[float], word_ids: List[int], chunk_size: int) -> torch.Tensor:
        """긴 프롬프트 청킹 처리"""
        
        chunks = []
        for i in range(0, len(tokens), chunk_size-2):  # 특수 토큰 공간 확보
            chunk_tokens = tokens[i:i+chunk_size-2]
            chunk_weights = weights[i:i+chunk_size-2]
            chunk_word_ids = word_ids[i:i+chunk_size-2]
            
            # 특수 토큰 추가
            full_tokens = [self.tokenizer.bos_token_id] + chunk_tokens + [self.tokenizer.eos_token_id]
            full_weights = [1.0] + chunk_weights + [1.0]
            full_word_ids = [0] + chunk_word_ids + [0]
            
            # 패딩
            while len(full_tokens) < chunk_size:
                full_tokens.append(self.tokenizer.pad_token_id or 0)
                full_weights.append(1.0)
                full_word_ids.append(0)
            
            # 인코딩
            token_tensor = torch.tensor([full_tokens], device=self.text_encoder.device)
            with torch.no_grad():
                chunk_emb = self.text_encoder(token_tensor)[0]
            
            # 가중치 적용
            if self.weight_mode == "A1111":
                chunk_emb = self._apply_a1111_weights(chunk_emb, full_weights, full_word_ids)
            elif self.weight_mode == "comfy++":
                chunk_emb = self._apply_comfy_weights(chunk_emb, full_weights, full_word_ids)
            
            chunks.append(chunk_emb)
        
        # 청크 병합 (평균)
        if len(chunks) == 1:
            return chunks[0]
        else:
            return torch.mean(torch.stack(chunks), dim=0)
    
    def _apply_a1111_weights(self, embeddings: torch.Tensor, weights: List[float], word_ids: List[int]) -> torch.Tensor:
        """A1111 스타일 가중치 적용"""
        weighted_emb = self.from_zero([weights], embeddings)
        
        # A1111 정규화
        norm_base = torch.linalg.norm(embeddings)
        norm_weighted = torch.linalg.norm(weighted_emb)
        
        if norm_weighted > 0:
            embeddings_final = (norm_base / norm_weighted) * weighted_emb
        else:
            embeddings_final = weighted_emb
        
        return embeddings_final
    
    def _apply_comfy_weights(self, embeddings: torch.Tensor, weights: List[float], word_ids: List[int]) -> torch.Tensor:
        """ComfyUI++ 스타일 가중치 적용 (고급)"""
        
        # 길이별 가중치 분배
        weights_normalized = self.divide_length([word_ids], [weights])[0]
        
        # 가중치 적용
        weighted_emb = self.from_zero([weights_normalized], embeddings)
        
        # 분포 복원
        fixed_std = (embeddings.std() / weighted_emb.std()) * (weighted_emb - weighted_emb.mean())
        embeddings_final = fixed_std + (embeddings.mean() - fixed_std.mean())
        
        return embeddings_final 