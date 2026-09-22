const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require.resolve('../web/app.js'),'utf8');
const code=source.slice(source.indexOf('async function syncVoiceSelection()'),source.indexOf('function renderBatch()'));
(async()=>{
 const calls=[],ctx={batch:{id:'b',files:[{id:'one'},{id:'two'}]},current:{batch:'b',id:'one'},busy:false,api:async(p,d)=>calls.push(d)};
 vm.createContext(ctx);vm.runInContext(code,ctx);
 await ctx.syncVoiceSelection();assert.equal(calls[0].id,'one');
 await ctx.syncVoiceSelection();assert.equal(calls.length,1);
 ctx.current.id='two';ctx.busy=true;await ctx.syncVoiceSelection();assert.equal(calls.length,1);
 ctx.busy=false;await ctx.syncVoiceSelection();assert.equal(calls[1].id,'two');
 ctx.current.id='removed';await ctx.syncVoiceSelection();assert.equal(calls.length,2);
 ctx.current={batch:'other',id:'one'};await ctx.syncVoiceSelection();assert.equal(calls.length,2);
 ctx.current={batch:'b',id:'one'};ctx.api=async()=>{throw Error('temporary')};await assert.rejects(ctx.syncVoiceSelection());assert.equal(ctx.batch.selected_id,'two');
 ctx.api=async(p,d)=>calls.push(d);await ctx.syncVoiceSelection();assert.equal(calls[2].id,'one');
 console.log('PASS: voice selection follows the displayed portrait, defers busy updates, and retries failures');
})().catch(e=>{console.error(e);process.exitCode=1});
