"""
AI Analyzer - LLM Client
Secure wrapper for OpenAI API with strict safety guards and fallback handling.
"""

import os
import json
import time
import hashlib
from typing import Optional, Dict, Any
from openai import OpenAI, OpenAIError
from pydantic import ValidationError

from .ai_analyzer_schemas import (
    AnalyzerInput,
    AnalyzerOutput,
    FALLBACK_OUTPUT,
    SYSTEM_PROMPT,
    MarketState
)


class AnalyzerLLMClient:
    """
    Secure LLM client for AI Analyzer.
    
    Responsibilities:
    - Format prompts with strict schema adherence
    - Call OpenAI API with timeout and error handling
    - Validate output schema
    - Detect and block prompt injection
    - Return deterministic fallback on any failure
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",  # Fast, cost-effective model
        timeout_seconds: int = 10,
        max_tokens: int = 800
    ):
        """
        Initialize LLM client.
        
        Args:
            api_key: OpenAI API key (defaults to env var OPENAI_API_KEY)
            model: Model identifier
            timeout_seconds: Request timeout
            max_tokens: Maximum tokens for response
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key required (set OPENAI_API_KEY env var)")
        
        self.client = OpenAI(api_key=self.api_key, timeout=timeout_seconds)
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens
        
        # Safety tracking
        self.blocked_count = 0
        self.fallback_count = 0
        self.total_calls = 0
    
    def explain(
        self,
        analyzer_input: AnalyzerInput
    ) -> Dict[str, Any]:
        """
        Generate explanation from analyzer input.
        
        Args:
            analyzer_input: Validated analyzer input
        
        Returns:
            Dict with:
                - output: AnalyzerOutput or fallback
                - success: bool
                - response_time_ms: int
                - tokens_used: int | None
                - blocked: bool
                - block_reason: str | None
                - fallback_triggered: bool
        """
        self.total_calls += 1
        start_time = time.time()
        
        result = {
            "output": None,
            "success": False,
            "response_time_ms": 0,
            "tokens_used": None,
            "blocked": False,
            "block_reason": None,
            "fallback_triggered": False
        }
        
        try:
            # Step 1: Validate input (should already be validated, but double-check)
            if not self._validate_input_safety(analyzer_input):
                result["blocked"] = True
                result["block_reason"] = "Input failed safety validation"
                result["output"] = self._get_fallback(analyzer_input.state)
                result["fallback_triggered"] = True
                self.blocked_count += 1
                return result
            
            # Step 2: Build user message (structured JSON only)
            user_message = self._build_user_message(analyzer_input)
            
            # Step 3: Call OpenAI API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.3,  # Low temperature for consistency
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"}  # Force JSON output
            )
            
            response_time_ms = int((time.time() - start_time) * 1000)
            result["response_time_ms"] = response_time_ms
            if response.usage:
                result["tokens_used"] = response.usage.total_tokens
            
            # Step 4: Parse and validate output
            raw_output = response.choices[0].message.content
            
            try:
                if raw_output:
                    parsed_output = json.loads(raw_output)
                else:
                    raise ValueError("Empty response from LLM")
                analyzer_output = AnalyzerOutput(**parsed_output)
                
                # Step 5: Validate state alignment
                if analyzer_output.bottom_line.state_alignment != analyzer_input.state:
                    result["blocked"] = True
                    result["block_reason"] = f"State mismatch: input={analyzer_input.state}, output={analyzer_output.bottom_line.state_alignment}"
                    result["output"] = self._get_fallback(analyzer_input.state)
                    result["fallback_triggered"] = True
                    self.blocked_count += 1
                    return result
                
                # Step 6: Check for banned terms (additional safety layer)
                if self._contains_banned_terms(analyzer_output):
                    result["blocked"] = True
                    result["block_reason"] = "Output contains banned betting terms"
                    result["output"] = self._get_fallback(analyzer_input.state)
                    result["fallback_triggered"] = True
                    self.blocked_count += 1
                    return result
                
                # Success!
                result["output"] = analyzer_output
                result["success"] = True
                return result
                
            except (json.JSONDecodeError, ValidationError) as e:
                # Schema validation failed - return fallback
                result["fallback_triggered"] = True
                result["block_reason"] = f"Schema validation failed: {str(e)}"
                result["output"] = self._get_fallback(analyzer_input.state)
                self.fallback_count += 1
                return result
        
        except OpenAIError as e:
            # API error - return fallback
            result["fallback_triggered"] = True
            result["block_reason"] = f"OpenAI API error: {str(e)}"
            result["output"] = self._get_fallback(analyzer_input.state)
            result["response_time_ms"] = int((time.time() - start_time) * 1000)
            self.fallback_count += 1
            return result
        
        except Exception as e:
            # Unexpected error - return fallback
            result["fallback_triggered"] = True
            result["block_reason"] = f"Unexpected error: {str(e)}"
            result["output"] = self._get_fallback(analyzer_input.state)
            result["response_time_ms"] = int((time.time() - start_time) * 1000)
            self.fallback_count += 1
            return result
    
    def _validate_input_safety(self, analyzer_input: AnalyzerInput) -> bool:
        """
        Validate input for safety violations.
        
        Args:
            analyzer_input: Input to validate
        
        Returns:
            True if safe, False if blocked
        """
        # Check for excessively long team names (potential injection)
        if len(analyzer_input.game.home) > 10 or len(analyzer_input.game.away) > 10:
            return False
        
        # Check for suspicious characters in team codes
        suspicious_chars = ['<', '>', '{', '}', 'script', 'prompt', 'ignore']
        for team in [analyzer_input.game.home, analyzer_input.game.away]:
            for char in suspicious_chars:
                if char in team.lower():
                    return False
        
        # Check for excessive reason codes (potential overflow)
        if len(analyzer_input.reason_codes) > 10:
            return False
        
        return True
    
    def _build_user_message(self, analyzer_input: AnalyzerInput) -> str:
        """
        Build user message with structured JSON only.
        
        Args:
            analyzer_input: Validated input
        
        Returns:
            JSON string for user message
        """
        # Convert to dict and serialize
        input_dict = analyzer_input.dict()
        
        # Add explicit instruction
        wrapper = {
            "instruction": "Explain the following game analysis using ONLY the provided data. Output valid JSON matching the required schema.",
            "data": input_dict
        }
        
        return json.dumps(wrapper, indent=2)
    
    def _contains_banned_terms(self, output: AnalyzerOutput) -> bool:
        """
        Check if output contains banned betting terms.
        
        Args:
            output: Output to check
        
        Returns:
            True if banned terms found, False otherwise
        """
        banned_terms = [
            'bet', 'take', 'lock', 'hammer', 'unit', 'stake', 
            'wager', 'parlay', 'play this', 'bet this', 'guaranteed'
        ]
        
        # Check all text fields
        all_text = (
            output.headline + ' ' +
            ' '.join(output.what_model_sees) + ' ' +
            ' '.join(output.key_risks) + ' ' +
            ' '.join(output.sharp_interpretation) + ' ' +
            output.bottom_line.recommended_behavior + ' ' +
            ' '.join(output.bottom_line.do_not_do)
        ).lower()
        
        for term in banned_terms:
            if term in all_text:
                return True
        
        return False
    
    def _get_fallback(self, state: MarketState) -> AnalyzerOutput:
        """
        Get fallback output with correct state alignment.
        
        Args:
            state: Current game state
        
        Returns:
            Fallback AnalyzerOutput
        """
        fallback = FALLBACK_OUTPUT.copy(deep=True)
        fallback.bottom_line.state_alignment = state
        return fallback
    
    def get_stats(self) -> Dict[str, int]:
        """
        Get client statistics.
        
        Returns:
            Dict with blocked_count, fallback_count, total_calls
        """
        return {
            "total_calls": self.total_calls,
            "blocked_count": self.blocked_count,
            "fallback_count": self.fallback_count,
            "success_count": self.total_calls - self.blocked_count - self.fallback_count
        }
    
    @staticmethod
    def compute_input_hash(analyzer_input: AnalyzerInput) -> str:
        """
        Compute deterministic hash of input for caching.
        
        Args:
            analyzer_input: Input to hash
        
        Returns:
            SHA256 hex digest
        """
        # Serialize to JSON with sorted keys for determinism
        json_str = analyzer_input.json(sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()
    
    @staticmethod
    def compute_output_hash(analyzer_output: AnalyzerOutput) -> str:
        """
        Compute deterministic hash of output for audit.
        
        Args:
            analyzer_output: Output to hash
        
        Returns:
            SHA256 hex digest
        """
        json_str = analyzer_output.json(sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()
