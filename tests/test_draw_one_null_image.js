const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require.resolve('../web/app.js'),'utf8');
const code=source.slice(source.indexOf('function geometry(c)'),source.indexOf('function draw(){'));

function makeCtx(){
 const calls=[];
 const ctx={fillStyle:'',strokeStyle:'',lineWidth:0,globalAlpha:1};
 for(const m of ['setTransform','fillRect','save','restore','beginPath','rect','clip','translate','rotate','drawImage','strokeRect','moveTo','lineTo','closePath','fill','stroke','setLineDash'])
  ctx[m]=(...a)=>calls.push([m,...a]);
 ctx.createPattern=()=>'pattern';
 ctx.calls=calls;
 return ctx;
}
function makeCanvas(fakeCtx){return {clientWidth:200,clientHeight:150,width:0,height:0,getContext:()=>fakeCtx}}

function run(state){
 const fakeCtx=makeCtx();
 const els={viewZoom:{value:'fit'},guide:{checked:false}};
 const ctx={
  window:{devicePixelRatio:1},
  $:id=>els[id],
  canvas:(w,h)=>({width:w,height:h,getContext:()=>makeCtx()}),
  checkerTile:{},
  viewShift:{x:0,y:0},
  before:false,mode:'image',cutoutVisible:false,stroke:null,guideEditing:false,overlay:null,
  reviewPreview:null,comparisonImg:null,comparisonKind:'mask',
  ...state,
 };
 vm.createContext(ctx);vm.runInContext(code,ctx);
 ctx.drawOne(makeCanvas(fakeCtx),false);
 return fakeCtx.calls;
}

const batch={canvas:{width:100,height:100}},current={transform:{x:0,y:0,scale:1,rotation:0},width:100,height:100};

// preview still null (mid-selection-switch gap): must not touch save/restore/drawImage at all.
let calls=run({preview:null,current,batch});
assert.equal(calls.filter(c=>c[0]==='save').length,0);
assert.equal(calls.filter(c=>c[0]==='restore').length,0);
assert.equal(calls.filter(c=>c[0]==='drawImage').length,0);

// preview ready but before-toggle is on and originalImg hasn't loaded yet
// (the new deferred-load gap): same -- must bail before any save(), not leave
// an unbalanced save stack for the next draw.
calls=run({preview:{},current,batch,before:true,originalImg:null});
assert.equal(calls.filter(c=>c[0]==='save').length,0);
assert.equal(calls.filter(c=>c[0]==='restore').length,0);
assert.equal(calls.filter(c=>c[0]==='drawImage').length,0);

// normal path: everything loaded -- draws, and save()/restore() stay balanced.
calls=run({preview:{},current,batch,before:false});
assert.equal(calls.filter(c=>c[0]==='save').length,2);
assert.equal(calls.filter(c=>c[0]==='restore').length,2);
assert.equal(calls.filter(c=>c[0]==='drawImage').length,1);

console.log('PASS: drawOne never draws a stale/missing image and never leaves an unbalanced save() stack');
