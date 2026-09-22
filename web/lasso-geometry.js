/* Pointer hit-testing in screen pixels, including non-square source images. */
(function(root){
 'use strict';
 function nearestSegment(points,p,sx,sy,closed){
  let best=null;
  for(let i=0;i<points.length-(closed?0:1);i++){
   const a=points[i],b=points[(i+1)%points.length];
   const vx=(b[0]-a[0])*sx,vy=(b[1]-a[1])*sy,px=(p[0]-a[0])*sx,py=(p[1]-a[1])*sy;
   const u=Math.max(0,Math.min(1,(px*vx+py*vy)/(vx*vx+vy*vy||1)));
   const distance=Math.hypot(px-u*vx,py-u*vy);
   if(!best||distance<best.distance)best={index:i+1,distance};
  }
  return best;
 }
 function pointAction(polygon,p,sx,sy,{add=false,remove=false}={}){
  let hit=-1,best=10;
  polygon.points.forEach((q,i)=>{const d=Math.hypot((q[0]-p[0])*sx,(q[1]-p[1])*sy);if(d<best){hit=i;best=d}});
  if(remove)return {type:hit>=0?'remove':'none',index:hit};
  if(add){const segment=nearestSegment(polygon.points,p,sx,sy,polygon.closed);return {type:'insert',index:segment&&(polygon.closed||segment.distance<9)?segment.index:polygon.points.length}}
  if(hit===0&&!polygon.closed&&polygon.points.length>=3)return {type:'close'};
  if(hit>=0)return {type:'drag',index:hit};
  if(!polygon.closed)return {type:'insert',index:polygon.points.length};
  const segment=nearestSegment(polygon.points,p,sx,sy,true);
  return segment&&segment.distance<9?{type:'insert',index:segment.index}:{type:'none'};
 }
 const api={nearestSegment,pointAction};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.LassoGeometry=api;
})(typeof window==='undefined'?globalThis:window);
