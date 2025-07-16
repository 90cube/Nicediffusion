"""
프롬프트 처리 도메인 로직
BREAK 키워드, 가중치 구문, 토큰 최적화, 청킹 등을 담당
"""

import re
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
import torch


@dataclass
class PromptAnalysis:
    """프롬프트 분석 결과"""
    token_count: int
    segments: List[str]
    weights: Dict[str, float]
    suggestions: List[str]
    is_optimized: bool
    truncated_parts: List[str]  # 잘린 부분 추적


@dataclass
class WeightedPrompt:
    """가중치가 적용된 프롬프트"""
    original: str
    processed: str
    weights: Dict[str, float]
    token_count: int
    chunks: List['PromptChunk']  # 청킹된 프롬프트


@dataclass
class PromptChunk:
    """프롬프트 청크"""
    text: str
    token_count: int
    importance_score: float
    chunk_type: str  # 'main', 'style', 'quality', 'detail'


class PromptProcessor:
    """고급 프롬프트 처리기"""
    
    def __init__(self, model_type='SD15'):
        # SDXL은 225 토큰, SD15는 77 토큰 지원
        self.model_type = model_type
        self.max_tokens = 225 if model_type == 'SDXL' else 77
        self.warning_threshold = 200 if model_type == 'SDXL' else 70
        self.break_keyword = "BREAK"
        
        # 가중치 패턴 정규식
        self.weight_pattern = r'\(([^:)]+)(?::([0-9]*\.?[0-9]+))?\)'
        self.negative_weight_pattern = r'\[([^\]]+)\]'
        
        # 키워드 중요도 점수 (높을수록 중요)
        self.importance_scores = {
            # 메인 콘셉트 (가장 중요)
            'portrait': 10, 'landscape': 10, 'character': 10, 'scene': 10,
            # 스타일 (중요)
            'anime': 8, 'realistic': 8, 'cartoon': 8, 'oil painting': 8,
            'watercolor': 8, 'digital art': 8, 'photography': 8,
            # 품질 (중간)
            'high quality': 6, 'masterpiece': 6, 'best quality': 6,
            'detailed': 6, 'sharp focus': 6, 'professional': 6,
            # 세부사항 (낮음)
            'lighting': 4, 'composition': 4, 'background': 4,
            'clothing': 3, 'accessories': 3, 'texture': 3,
        }
    
    def process_prompt(self, prompt: str, tokenizer=None) -> WeightedPrompt:
        """고급 프롬프트 처리 (BREAK 키워드, 가중치 구문, 청킹)"""
        if not prompt.strip():
            return WeightedPrompt(
                original=prompt,
                processed=prompt,
                weights={},
                token_count=0,
                chunks=[]
            )
        
        # 1. BREAK 키워드로 세그먼트 분리
        segments = self._split_by_break(prompt)
        
        # 2. 가중치 추출 및 처리
        weights = self._extract_weights(prompt)
        
        # 3. 가중치 제거된 깨끗한 프롬프트 생성
        clean_prompt = self._remove_weight_syntax(prompt)
        
        # 4. 토큰 수 계산
        token_count = self._calculate_token_count(clean_prompt, tokenizer)
        
        # 5. 토큰 제한 초과 시 지능적 최적화
        if token_count > self.max_tokens:
            optimized_prompt = self._intelligent_truncation(clean_prompt, tokenizer)
            token_count = self._calculate_token_count(optimized_prompt, tokenizer)
            clean_prompt = optimized_prompt
        
        # 6. 청킹 처리
        chunks = self._create_chunks(clean_prompt, tokenizer)
        
        return WeightedPrompt(
            original=prompt,
            processed=clean_prompt,
            weights=weights,
            token_count=token_count,
            chunks=chunks
        )
    
    def _intelligent_truncation(self, prompt: str, tokenizer=None) -> str:
        """지능적 프롬프트 자르기 (중요도 기반)"""
        if not prompt.strip():
            return prompt
        
        # 1. 키워드별로 분할
        keywords = [kw.strip() for kw in prompt.split(',')]
        
        # 2. 각 키워드의 중요도 점수 계산
        keyword_scores = []
        for keyword in keywords:
            score = 0
            for pattern, importance in self.importance_scores.items():
                if pattern.lower() in keyword.lower():
                    score = max(score, importance)
            keyword_scores.append((keyword, score))
        
        # 3. 중요도 순으로 정렬
        keyword_scores.sort(key=lambda x: x[1], reverse=True)
        
        # 4. 토큰 제한 내에서 최대한 많은 중요 키워드 포함
        selected_keywords = []
        current_tokens = 0
        
        for keyword, score in keyword_scores:
            keyword_tokens = self._calculate_token_count(keyword, tokenizer)
            if current_tokens + keyword_tokens <= self.max_tokens:
                selected_keywords.append(keyword)
                current_tokens += keyword_tokens
            else:
                break
        
        # 5. 선택된 키워드로 프롬프트 재구성
        optimized_prompt = ', '.join(selected_keywords)
        
        print(f"🔧 지능적 최적화: {len(keywords)}개 키워드 → {len(selected_keywords)}개 키워드")
        print(f"   제거된 키워드: {[kw for kw, _ in keyword_scores if kw not in selected_keywords]}")
        
        return optimized_prompt
    
    def _create_chunks(self, prompt: str, tokenizer=None) -> List[PromptChunk]:
        """프롬프트를 의미적 청크로 분할"""
        if not prompt.strip():
            return []
        
        chunks = []
        keywords = [kw.strip() for kw in prompt.split(',')]
        
        # 청크 타입 분류
        main_keywords = []
        style_keywords = []
        quality_keywords = []
        detail_keywords = []
        
        for keyword in keywords:
            if any(pattern in keyword.lower() for pattern in ['portrait', 'landscape', 'character', 'scene']):
                main_keywords.append(keyword)
            elif any(pattern in keyword.lower() for pattern in ['anime', 'realistic', 'cartoon', 'painting', 'art']):
                style_keywords.append(keyword)
            elif any(pattern in keyword.lower() for pattern in ['quality', 'masterpiece', 'detailed', 'sharp']):
                quality_keywords.append(keyword)
            else:
                detail_keywords.append(keyword)
        
        # 청크 생성
        if main_keywords:
            chunks.append(PromptChunk(
                text=', '.join(main_keywords),
                token_count=self._calculate_token_count(', '.join(main_keywords), tokenizer),
                importance_score=10,
                chunk_type='main'
            ))
        
        if style_keywords:
            chunks.append(PromptChunk(
                text=', '.join(style_keywords),
                token_count=self._calculate_token_count(', '.join(style_keywords), tokenizer),
                importance_score=8,
                chunk_type='style'
            ))
        
        if quality_keywords:
            chunks.append(PromptChunk(
                text=', '.join(quality_keywords),
                token_count=self._calculate_token_count(', '.join(quality_keywords), tokenizer),
                importance_score=6,
                chunk_type='quality'
            ))
        
        if detail_keywords:
            chunks.append(PromptChunk(
                text=', '.join(detail_keywords),
                token_count=self._calculate_token_count(', '.join(detail_keywords), tokenizer),
                importance_score=4,
                chunk_type='detail'
            ))
        
        return chunks
    
    def analyze_prompt(self, prompt: str, tokenizer=None) -> PromptAnalysis:
        """고급 프롬프트 분석 및 최적화 제안"""
        processed = self.process_prompt(prompt, tokenizer)
        segments = self._split_by_break(processed.processed)
        
        suggestions = []
        is_optimized = True
        truncated_parts = []
        
        # 토큰 수 기반 제안
        if processed.token_count > self.max_tokens:
            suggestions.append(f"⚠️ 토큰 수({processed.token_count})가 제한({self.max_tokens})을 초과했습니다")
            suggestions.append("💡 지능적 최적화가 적용되었습니다")
            suggestions.append("💡 BREAK 키워드로 의미적 그룹을 분리하세요")
            is_optimized = False
        elif processed.token_count > self.warning_threshold:
            suggestions.append(f"⚠️ 토큰 수({processed.token_count})가 경계선에 있습니다")
            suggestions.append("💡 BREAK 키워드 사용을 고려하세요")
        
        # 청크 분석
        if processed.chunks:
            suggestions.append(f"✅ {len(processed.chunks)}개의 의미적 청크로 분할되었습니다")
            for chunk in processed.chunks:
                suggestions.append(f"   - {chunk.chunk_type}: {chunk.text[:30]}... ({chunk.token_count} 토큰)")
        
        # 세그먼트 분석
        if len(segments) > 1:
            suggestions.append("✅ BREAK 키워드로 잘 구조화되어 있습니다")
        else:
            suggestions.append("💡 BREAK 키워드로 의미적 그룹을 분리하면 더 나은 결과를 얻을 수 있습니다")
        
        # 가중치 분석
        if processed.weights:
            suggestions.append("✅ 가중치 구문이 적용되어 있습니다")
            for keyword, weight in processed.weights.items():
                if weight > 1.5:
                    suggestions.append(f"⚠️ '{keyword}'의 가중치({weight})가 너무 높습니다 (1.5 이하 권장)")
                elif weight < 0.5:
                    suggestions.append(f"⚠️ '{keyword}'의 가중치({weight})가 너무 낮습니다 (0.5 이상 권장)")
        
        return PromptAnalysis(
            token_count=processed.token_count,
            segments=segments,
            weights=processed.weights,
            suggestions=suggestions,
            is_optimized=is_optimized,
            truncated_parts=truncated_parts
        )
    
    def _split_by_break(self, prompt: str) -> List[str]:
        """BREAK 키워드로 프롬프트 분할"""
        if not prompt.strip():
            return []
        
        # BREAK 키워드로 분할 (대소문자 구분 없이)
        segments = re.split(r'\bBREAK\b', prompt, flags=re.IGNORECASE)
        
        # 빈 세그먼트 제거 및 공백 정리
        segments = [seg.strip() for seg in segments if seg.strip()]
        
        return segments
    
    def _extract_weights(self, prompt: str) -> Dict[str, float]:
        """가중치 구문 추출"""
        weights = {}
        
        # 양의 가중치: (키워드:1.2) 또는 (키워드)
        for match in re.finditer(self.weight_pattern, prompt):
            keyword = match.group(1).strip()
            weight_str = match.group(2)
            
            if weight_str:
                try:
                    weight = float(weight_str)
                except ValueError:
                    weight = 1.1  # 기본값
            else:
                weight = 1.1  # (키워드)는 1.1과 동일
            
            weights[keyword] = weight
        
        # 음의 가중치: [키워드] (0.9와 동일)
        for match in re.finditer(self.negative_weight_pattern, prompt):
            keyword = match.group(1).strip()
            weights[keyword] = 0.9
        
        return weights
    
    def _remove_weight_syntax(self, prompt: str) -> str:
        """가중치 구문 제거"""
        # 양의 가중치 제거
        clean_prompt = re.sub(self.weight_pattern, r'\1', prompt)
        
        # 음의 가중치 제거
        clean_prompt = re.sub(self.negative_weight_pattern, r'\1', clean_prompt)
        
        return clean_prompt.strip()
    
    def _calculate_token_count(self, prompt: str, tokenizer=None) -> int:
        """정확한 토큰 수 계산"""
        if not prompt.strip():
            return 0
        
        if tokenizer:
            try:
                # 실제 토크나이저 사용
                text_inputs = tokenizer(
                    prompt,
                    padding="longest",
                    truncation=False,
                    return_tensors="pt",
                )
                input_ids = text_inputs.input_ids[0]
                return len(input_ids)
            except Exception as e:
                print(f"⚠️ 토크나이저 계산 중 오류: {e}")
                # 오류 시 간단한 추정으로 폴백
        
        # 간단한 추정 (공백으로 분할)
        return len(prompt.split())
    
    def get_custom_tokenizer(self, state_manager=None):
        """커스텀 토크나이저 가져오기"""
        if state_manager and hasattr(state_manager, 'tokenizer_manager'):
            return state_manager.tokenizer_manager.get_current_tokenizer()
        return None
    
    def add_break_keyword(self, prompt: str, position: Optional[int] = None) -> str:
        """BREAK 키워드 추가"""
        if position is None:
            # 문장 끝에 추가
            return f"{prompt} {self.break_keyword}"
        else:
            # 지정된 위치에 추가
            return prompt[:position] + f" {self.break_keyword} " + prompt[position:]
    
    def apply_weight(self, keyword: str, weight: float = 1.1) -> str:
        """가중치 구문 생성"""
        if weight == 1.0:
            return keyword
        elif weight < 1.0:
            return f"[{keyword}]"  # 음의 가중치는 대괄호 사용
        else:
            return f"({keyword}:{weight})"
    
    def create_prompt_embeddings(self, prompt: str, tokenizer=None, text_encoder=None) -> Optional[torch.Tensor]:
        """프롬프트 임베딩 직접 생성"""
        if not tokenizer or not text_encoder:
            return None
        
        try:
            # 토큰화
            text_inputs = tokenizer(
                prompt,
                padding="max_length",
                max_length=self.max_tokens,
                truncation=True,
                return_tensors="pt",
            )
            
            # 임베딩 생성
            with torch.no_grad():
                prompt_embeds = text_encoder(text_inputs.input_ids)[0]
            
            return prompt_embeds
            
        except Exception as e:
            print(f"⚠️ 프롬프트 임베딩 생성 실패: {e}")
            return None
    
    def optimize_prompt(self, prompt: str, target_tokens: int = 70) -> str:
        """프롬프트를 토큰 제한 내에서 최적화"""
        if not prompt.strip():
            return prompt
        
        # 1. 기본 정리
        optimized = self._clean_prompt(prompt)
        
        # 2. 토큰 수 확인
        token_count = self._calculate_token_count(optimized)
        
        if token_count <= target_tokens:
            return optimized
        
        # 3. 토큰 제한 초과 시 지능적 최적화
        print(f"🔧 프롬프트 최적화: {token_count} → {target_tokens} 토큰")
        
        # 3-1. 불필요한 쉼표와 공백 제거
        optimized = self._remove_redundant_commas(optimized)
        
        # 3-2. 중복 키워드 제거
        optimized = self._remove_duplicate_keywords(optimized)
        
        # 3-3. 토큰 수 재확인
        token_count = self._calculate_token_count(optimized)
        
        if token_count <= target_tokens:
            return optimized
        
        # 3-4. 지능적 자르기 적용
        optimized = self._intelligent_truncation(optimized, None)
        
        # 3-5. 최종 토큰 수 확인
        final_token_count = self._calculate_token_count(optimized)
        print(f"✅ 최적화 완료: {final_token_count} 토큰")
        
        return optimized
    
    def _clean_prompt(self, prompt: str) -> str:
        """프롬프트 기본 정리"""
        # 여러 공백을 하나로
        cleaned = ' '.join(prompt.split())
        # 쉼표 뒤 공백 정리
        cleaned = cleaned.replace(', ', ',')
        cleaned = cleaned.replace(',', ', ')
        # 끝 쉼표 제거
        cleaned = cleaned.rstrip(', ')
        return cleaned
    
    def _remove_redundant_commas(self, prompt: str) -> str:
        """불필요한 쉼표 제거"""
        # 연속된 쉼표 제거
        cleaned = re.sub(r',\s*,+', ',', prompt)
        # 쉼표-공백-쉼표 패턴 정리
        cleaned = re.sub(r',\s+,', ',', cleaned)
        return cleaned
    
    def _remove_duplicate_keywords(self, prompt: str) -> str:
        """중복 키워드 제거"""
        keywords = [kw.strip() for kw in prompt.split(',')]
        unique_keywords = []
        seen = set()
        
        for keyword in keywords:
            if keyword.lower() not in seen:
                unique_keywords.append(keyword)
                seen.add(keyword.lower())
        
        return ', '.join(unique_keywords)
    
    def _remove_less_important_keywords(self, prompt: str, target_tokens: int) -> str:
        """덜 중요한 키워드 제거"""
        keywords = [kw.strip() for kw in prompt.split(',')]
        
        # 키워드별 중요도 점수 계산
        keyword_scores = []
        for keyword in keywords:
            score = 0
            for pattern, importance in self.importance_scores.items():
                if pattern.lower() in keyword.lower():
                    score = max(score, importance)
            keyword_scores.append((keyword, score))
        
        # 중요도 순으로 정렬
        keyword_scores.sort(key=lambda x: x[1], reverse=True)
        
        # 토큰 제한 내에서 최대한 많은 중요 키워드 포함
        selected_keywords = []
        current_tokens = 0
        
        for keyword, score in keyword_scores:
            keyword_tokens = len(keyword.split())  # 간단한 토큰 추정
            if current_tokens + keyword_tokens <= target_tokens:
                selected_keywords.append(keyword)
                current_tokens += keyword_tokens
            else:
                break
        
        return ', '.join(selected_keywords) 