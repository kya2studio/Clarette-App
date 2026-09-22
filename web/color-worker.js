'use strict';
importScripts('curve-math.js');
const RANGE_CENTERS={red:0,yellow:60,green:120,cyan:180,blue:240,magenta:300};
// imaging.py seeds grain with a fixed RNG specifically so the texture stays
// put across repeated renders of the same edit (only strength should move
// with the slider, not the pattern itself) -- Math.random() here defeated
// that on every redraw (loupe move, any other slider), so the exported
// grain never looked like the preview. A cheap deterministic hash of the
// pixel index gives the same "some pixels lighter, some darker" texture
// without a fresh draw every frame.
function grainNoise(i){const x=Math.sin(i*12.9898)*43758.5453;return x-Math.floor(x)}
function adjustPixels(c,col){const ctx=c.getContext('2d',{willReadFrequently:true}),im=ctx.getImageData(0,0,c.width,c.height),a=im.data;const maps=['red','green','blue'].map(ch=>Array.from({length:256},(_,i)=>interp(interp(i/255,col[ch]),col.rgb)));
 const rangeEntries=Object.entries(col.color_ranges||{}).filter(([,v])=>v.hue||v.saturation||v.lightness);
 const exposure=col.exposure||0,lightness=col.lightness||0,grain=col.grain||0;
 for(let i=0;i<a.length;i+=4){let r=maps[0][a[i]],g=maps[1][a[i+1]],b=maps[2][a[i+2]];const temp=col.temperature||0,tint=col.tint||0,exp=1+exposure/100;r=Math.max(0,Math.min(1,r*(1+temp*.0015+tint*.0005)*exp));g=Math.max(0,Math.min(1,g*(1-tint*.001)*exp));b=Math.max(0,Math.min(1,b*(1-temp*.0015+tint*.0005)*exp));const lum=.2126*r+.7152*g+.0722*b;const d=col.shadows/100*.45*(1-lum)**3+col.highlights/100*.35*lum**3;r=Math.max(0,Math.min(1,r+d));g=Math.max(0,Math.min(1,g+d));b=Math.max(0,Math.min(1,b+d));
 if(col.hue||col.saturation||lightness||rangeEntries.length){const max=Math.max(r,g,b),min=Math.min(r,g,b),delta=max-min;let h=0;if(delta)h=max===r?((g-b)/delta)%6:max===g?(b-r)/delta+2:(r-g)/delta+4;h=((h*60)%360+360)%360;
  let hh=((h+col.hue)%360+360)%360,sat=Math.max(0,Math.min(1,(max?delta/max:0)*(1+col.saturation/100))),v=Math.max(0,Math.min(1,max*(1+lightness/100)));
  for(const [name,entry] of rangeEntries){const center=entry.center??RANGE_CENTERS[name],d=((h-center+180)%360+360)%360-180;let weight;if(entry.bounds){const [a,b,c,z]=entry.bounds;weight=Math.max(0,Math.min(1,d>=b?1:(d-a)/Math.max(b-a,1e-6),d<=c?1:(z-d)/Math.max(z-c,1e-6)))}else weight=Math.max(0,1-Math.abs(d)/60);if(!weight)continue;hh=((hh+weight*entry.hue)%360+360)%360;sat=Math.max(0,Math.min(1,sat*(1+weight*entry.saturation/100)));v=Math.max(0,Math.min(1,v*(1+weight*entry.lightness/100)))}
  const C=v*sat,X=C*(1-Math.abs((hh/60)%2-1)),m=v-C;let q=hh<60?[C,X,0]:hh<120?[X,C,0]:hh<180?[0,C,X]:hh<240?[0,X,C]:hh<300?[X,0,C]:[C,0,X];[r,g,b]=q.map(x=>x+m)}
 if(grain){const n=(grainNoise(i)-.5)*(grain/100*.08);r=Math.max(0,Math.min(1,r+n));g=Math.max(0,Math.min(1,g+n));b=Math.max(0,Math.min(1,b+n))}
 a[i]=Math.round(r*255);a[i+1]=Math.round(g*255);a[i+2]=Math.round(b*255)}ctx.putImageData(im,0,0);return c}

self.onmessage=({data:d})=>{try{const apply=pixels=>{const im={data:new Uint8ClampedArray(pixels)};const c={width:d.width,height:d.height,getContext:()=>({getImageData:()=>im,putImageData:()=>{}})};adjustPixels(c,d.color);return im.data.buffer};const pixels=apply(d.pixels),reviewPixels=d.reviewPixels?apply(d.reviewPixels):null;self.postMessage({id:d.id,pixels,reviewPixels},reviewPixels?[pixels,reviewPixels]:[pixels])}catch(e){self.postMessage({id:d.id,error:String(e)})}};
