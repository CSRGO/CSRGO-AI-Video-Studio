import {readFileSync} from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {bundle} from '@remotion/bundler';
import {openBrowser, selectComposition, renderMedia} from '@remotion/renderer';

const rendererDir=path.dirname(fileURLToPath(import.meta.url));
process.on('unhandledRejection',error=>{console.error(String(error?.message||error));process.exit(1);});
try {
  const project=JSON.parse(readFileSync(process.argv[2],'utf8'));
  const serveUrl=await bundle({entryPoint:project.entry,
    outDir:path.join(path.dirname(project.entry),'.bundle'),
    webpackOverride:config=>({...config,resolve:{...config.resolve,
      modules:[path.join(rendererDir,'node_modules'),...(config.resolve?.modules||[])],
      alias:{...config.resolve?.alias,react:path.join(rendererDir,'node_modules/react'),
        'react-dom':path.join(rendererDir,'node_modules/react-dom'),remotion:path.join(rendererDir,'node_modules/remotion')}
    }})});
  const browser=await openBrowser('chrome',{
    ...(process.env.REMOTION_BROWSER_EXECUTABLE?{browserExecutable:process.env.REMOTION_BROWSER_EXECUTABLE}:{}),
    logLevel:'error'});
  try {
    const composition=await selectComposition({serveUrl,id:'CSRGO',puppeteerInstance:browser,logLevel:'error'});
    let last=-1;
    await renderMedia({composition,serveUrl,codec:'h264',outputLocation:process.argv[3],
      puppeteerInstance:browser,concurrency:2,crf:18,pixelFormat:'yuv420p',logLevel:'error',
      licenseKey:process.env.REMOTION_PRIVATE_LICENSE_KEY||null,
      isProduction:process.env.CSRGO_RENDER_TEST!=='1',
      onProgress:({progress})=>{const pct=Math.floor(progress*100);if(pct>=last+5){last=pct;console.log(JSON.stringify({progress:pct}));}}});
  } finally {await browser.close({silent:true});}
} catch(error) {console.error(error.stack||error.message);process.exitCode=1;}
