import {expect,it} from 'vitest';
import {explanationLabel} from './routeInsight';
it('labels genuine provider use separately from allowance and validation fallback',()=>{
 expect(explanationLabel({mode:'gemini_arranged_approved_text',fallback_reason:null})).toContain('Gemini');
 expect(explanationLabel({mode:'deterministic',fallback_reason:'gemini_request_limit'})).toContain('allowance reached');
 expect(explanationLabel({mode:'deterministic',fallback_reason:'gemini_unavailable_or_invalid_output'})).toContain('could not be verified');
 expect(explanationLabel({mode:'untrusted markup',fallback_reason:'private-key'})).toBe('Deterministic summary · no LLM invoked');
});
