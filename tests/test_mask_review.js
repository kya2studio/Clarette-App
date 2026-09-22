const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
let response;
const ctx={self:{postMessage:d=>response=d},importScripts:()=>{},Uint8ClampedArray,Math};
vm.createContext(ctx);vm.runInContext(fs.readFileSync(require.resolve('../web/curve-math.js'),'utf8'),ctx);vm.runInContext(fs.readFileSync(require.resolve('../web/color-worker.js'),'utf8'),ctx);
const identity=[[0,0],[1,1]],color={rgb:identity,red:identity,green:identity,blue:identity,shadows:0,highlights:0,saturation:0,hue:0,temperature:20,exposure:10};
const run=(pixels,reviewPixels)=>{ctx.self.onmessage({data:{id:4,width:1,height:1,color,pixels:new Uint8ClampedArray(pixels).buffer,reviewPixels:reviewPixels&&new Uint8ClampedArray(reviewPixels).buffer}});assert.equal(response.error,undefined);return response};
const a=[40,20,10,255],b=[120,160,100,255];const pair=run(a,b),cut=Array.from(new Uint8ClampedArray(pair.pixels)),review=Array.from(new Uint8ClampedArray(pair.reviewPixels));
assert.deepEqual(cut,Array.from(new Uint8ClampedArray(run(a).pixels)));assert.deepEqual(review,Array.from(new Uint8ClampedArray(run(b).pixels)));assert.notDeepEqual(cut,review);
console.log('PASS: natural preview and cleaned cutout receive independent, identical color processing');
