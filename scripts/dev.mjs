// Starts only local development servers. No provisioning or provider requests.
import {spawn} from 'node:child_process';
import {existsSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const python=path.join(root,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
const vite=path.join(root,'frontend/node_modules/vite/bin/vite.js');
if(!existsSync(python)||!existsSync(vite)){console.error('Install the Python environment and run npm --prefix frontend ci first.');process.exit(1);}
const children=[
  spawn(python,['-m','uvicorn','ecoroute.main:app','--host','127.0.0.1','--port','8000','--no-access-log'],{cwd:root,stdio:'inherit',env:{...process.env,ECOROUTE_PROFILE:'local',CORS_ORIGINS:'["http://127.0.0.1:5173"]'}}),
  spawn(process.execPath,[vite,'--host','127.0.0.1','--port','5173','--strictPort'],{cwd:path.join(root,'frontend'),stdio:'inherit'}),
];
let stopping=false;
function stop(code=0){if(stopping)return;stopping=true;for(const child of children)child.kill();process.exitCode=code;}
for(const child of children){child.on('error',error=>{console.error(error.message);stop(1);});child.on('exit',code=>stop(code||0));}
process.on('SIGINT',()=>stop());process.on('SIGTERM',()=>stop());
