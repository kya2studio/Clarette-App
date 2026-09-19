// Monotone cubic Hermite curves: smooth at control points without ringing.
function interp(x,p){
 const n=p.length,h=[],d=[],m=[];for(let i=0;i<n-1;i++){h[i]=p[i+1][0]-p[i][0];d[i]=(p[i+1][1]-p[i][1])/h[i]}
 m[0]=d[0];m[n-1]=d[n-2];for(let i=1;i<n-1;i++){const a=d[i-1],b=d[i],w1=2*h[i]+h[i-1],w2=h[i]+2*h[i-1];m[i]=a*b<=0?0:(w1+w2)/(w1/a+w2/b)}
 if(x<=p[0][0])return p[0][1];if(x>=p[n-1][0])return p[n-1][1];let i=0;while(i<n-2&&x>p[i+1][0])i++;const t=(x-p[i][0])/h[i],t2=t*t,t3=t2*t;
 return Math.max(0,Math.min(1,(2*t3-3*t2+1)*p[i][1]+(t3-2*t2+t)*h[i]*m[i]+(-2*t3+3*t2)*p[i+1][1]+(t3-t2)*h[i]*m[i+1]));
}
