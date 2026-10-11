import {afterEach,expect,it,vi} from 'vitest';
afterEach(()=>{vi.unstubAllEnvs();vi.unstubAllGlobals();vi.resetModules();});
it('imports API configuration in Node without browser globals or a configured redirect',async()=>{
 vi.resetModules();vi.stubEnv('VITE_COGNITO_REDIRECT_URI','');vi.stubGlobal('window',undefined);
 const {config}=await import('./api');expect(config.redirect).toBe('');
});
it('retains the browser origin redirect when no explicit redirect is configured',async()=>{
 vi.resetModules();vi.stubEnv('VITE_COGNITO_REDIRECT_URI','');
 vi.stubGlobal('window',{location:{origin:'https://ecoroute.example'}});
 const {config}=await import('./api');expect(config.redirect).toBe('https://ecoroute.example/');
});
