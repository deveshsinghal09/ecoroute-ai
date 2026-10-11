export interface RouteExplanation {explanation:string;mode:string;fallback_reason:string|null}
export function explanationLabel(value?:Pick<RouteExplanation,'mode'|'fallback_reason'>) {
  if(value?.mode==='gemini_arranged_approved_text')return 'Gemini · grounded in server-calculated metrics';
  if(value?.mode==='bedrock_arranged_approved_text')return 'Bedrock · grounded in server-calculated metrics';
  const failures:Record<string,string>={
    gemini_provider_quota:'Gemini provider quota reached · check Google AI Studio quota and billing',
    gemini_access_denied:'Gemini access denied · check the backend key and API restrictions',
    gemini_model_unavailable:'Gemini model unavailable · check the configured model ID',
    gemini_request_rejected:'Gemini request rejected · check model compatibility and key configuration',
    gemini_secret_unavailable:'Gemini secret unavailable · check the Lambda secret reference and permissions',
    gemini_secret_invalid:'Gemini secret format invalid · use api_key JSON or plaintext',
    gemini_incomplete_or_blocked:'Gemini response incomplete or blocked · deterministic fallback retained',
    gemini_provider_unavailable:'Gemini temporarily unavailable · deterministic fallback retained',
  };
  if(value?.fallback_reason&&Object.prototype.hasOwnProperty.call(failures,value.fallback_reason))return failures[value.fallback_reason];
  if(value?.fallback_reason?.endsWith('_request_limit'))return 'Deterministic fallback · LLM request allowance reached';
  if(value?.fallback_reason?.endsWith('_unavailable_or_invalid_output'))return 'Deterministic fallback · LLM unavailable or response could not be verified';
  return 'Deterministic summary · no LLM invoked';
}
