import {transform} from 'esbuild';
import {readFileSync} from 'node:fs';
try {
  const source=readFileSync(process.argv[2], 'utf8');
  const imports=[...source.matchAll(/(?:from\s*|import\s*)['"]([^'"]+)['"]/g)].map(m=>m[1]);
  if(imports.some(name=>!['react','remotion'].includes(name))) throw new Error('Only react and remotion imports are supported.');
  if(/\b(?:fetch|XMLHttpRequest|WebSocket|setInterval|setTimeout|requestAnimationFrame)\s*\(/.test(source)) throw new Error('Use deterministic frame-driven animation without networking or timers.');
  if(!/export\s+default\b/.test(source)) throw new Error('Export a default React scene component.');
  await transform(source,{loader:'jsx',format:'esm'});
} catch(error){ console.error(error.message);process.exitCode=1; }
