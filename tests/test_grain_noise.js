const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
// grainNoise is duplicated verbatim in web/app.js and web/color-worker.js
// (see the comments at each definition) -- checked against both copies so
// a future edit to only one of them is caught here, not by a shimmering
// preview report.
for(const file of ['../web/app.js','../web/color-worker.js']){
 const source=fs.readFileSync(require.resolve(file),'utf8');
 const code=source.slice(source.indexOf('function grainNoise'));
 const ctx={};vm.createContext(ctx);vm.runInContext(code.slice(0,code.indexOf('}')+1),ctx);
 assert.equal(ctx.grainNoise(1234),ctx.grainNoise(1234),file+': same pixel index must give the same noise on every redraw');
 assert.notEqual(ctx.grainNoise(1234),ctx.grainNoise(1238),file+': different pixels should not all get identical noise');
 for(const i of [0,1,1234,999999])assert.ok(ctx.grainNoise(i)>=0&&ctx.grainNoise(i)<1,file+': noise must stay in [0,1) for grain/100*.08 scaling to behave');
}
console.log('PASS: grainNoise is deterministic per pixel index (matches imaging.py\'s seeded-RNG intent) in both app.js and color-worker.js');
