export interface RouteExplanation {explanation:string;mode:string;fallback_reason:string|null}
export function explanationLabel(value?:Pick<RouteExplanation,'mode'|'fallback_reason'>) {
  if(value?.mode==='gemini_arranged_approved_text')return 'Gemini · grounded in server-calculated metrics';
  if(value?.mode==='bedrock_arranged_approved_text')return 'Bedrock · grounded in server-calculated metrics';
  if(value?.fallback_reason?.endsWith('_request_limit'))return 'Deterministic fallback · LLM request allowance reached';
  if(value?.fallback_reason?.endsWith('_unavailable_or_invalid_output'))return 'Deterministic fallback · LLM unavailable or response could not be verified';
  return 'Deterministic summary · no LLM invoked';
}
