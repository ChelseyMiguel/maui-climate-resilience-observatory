/* esm.sh - troika-three-utils@0.49.0 */
import{ShaderChunk as O,UniformsUtils as E,MeshDepthMaterial as P,RGBADepthPacking as R,MeshDistanceMaterial as U,ShaderLib as S,Matrix4 as I,Vector3 as d,Mesh as N,CylinderGeometry as H,Vector2 as K,MeshStandardMaterial as L,DoubleSide as j}from"three";var k=/\bvoid\s+main\s*\(\s*\)\s*{/g;function _(t){let e=/^[ \t]*#include +<([\w\d./]+)>/gm;function i(o,r){let c=O[r];return c?_(c):o}return t.replace(e,i)}var s=[];for(let t=0;t<256;t++)s[t]=(t<16?"0":"")+t.toString(16);function G(){let t=Math.random()*4294967295|0,e=Math.random()*4294967295|0,i=Math.random()*4294967295|0,o=Math.random()*4294967295|0;return(s[t&255]+s[t>>8&255]+s[t>>16&255]+s[t>>24&255]+"-"+s[e&255]+s[e>>8&255]+"-"+s[e>>16&15|64]+s[e>>24&255]+"-"+s[i&63|128]+s[i>>8&255]+"-"+s[i>>16&255]+s[i>>24&255]+s[o&255]+s[o>>8&255]+s[o>>16&255]+s[o>>24&255]).toUpperCase()}var v=Object.assign||function(){let t=arguments[0];for(let e=1,i=arguments.length;e<i;e++){let o=arguments[e];if(o)for(let r in o)Object.prototype.hasOwnProperty.call(o,r)&&(t[r]=o[r])}return t},V=Date.now(),w=new WeakMap,b=new Map,F=1e10;function D(t,e){let i=Z(e),o=w.get(t);if(o||w.set(t,o=Object.create(null)),o[i])return new o[i];let r=`_onBeforeCompile${i}`,c=function(n,a){t.onBeforeCompile.call(this,n,a);let p=this.customProgramCacheKey()+"|"+n.vertexShader+"|"+n.fragmentShader,m=b[p];if(!m){let M=J(this,n,e,i);m=b[p]=M}n.vertexShader=m.vertexShader,n.fragmentShader=m.fragmentShader,v(n.uniforms,this.uniforms),e.timeUniform&&(n.uniforms[e.timeUniform]={get value(){return Date.now()-V}}),this[r]&&this[r](n)},l=function(){return f(e.chained?t:t.clone())},f=function(n){let a=Object.create(n,h);return Object.defineProperty(a,"baseMaterial",{value:t}),Object.defineProperty(a,"id",{value:F++}),a.uuid=G(),a.uniforms=v({},n.uniforms,e.uniforms),a.defines=v({},n.defines,e.defines),a.defines[`TROIKA_DERIVED_MATERIAL_${i}`]="",a.extensions=v({},n.extensions,e.extensions),a._listeners=void 0,a},h={constructor:{value:l},isDerivedMaterial:{value:!0},customProgramCacheKey:{writable:!0,configurable:!0,value:function(){return t.customProgramCacheKey()+"|"+i}},onBeforeCompile:{get(){return c},set(n){this[r]=n}},copy:{writable:!0,configurable:!0,value:function(n){return t.copy.call(this,n),!t.isShaderMaterial&&!t.isDerivedMaterial&&(v(this.extensions,n.extensions),v(this.defines,n.defines),v(this.uniforms,E.clone(n.uniforms))),this}},clone:{writable:!0,configurable:!0,value:function(){let n=new t.constructor;return f(n).copy(this)}},getDepthMaterial:{writable:!0,configurable:!0,value:function(){let n=this._depthMaterial;return n||(n=this._depthMaterial=D(t.isDerivedMaterial?t.getDepthMaterial():new P({depthPacking:R}),e),n.defines.IS_DEPTH_MATERIAL="",n.uniforms=this.uniforms),n}},getDistanceMaterial:{writable:!0,configurable:!0,value:function(){let n=this._distanceMaterial;return n||(n=this._distanceMaterial=D(t.isDerivedMaterial?t.getDistanceMaterial():new U,e),n.defines.IS_DISTANCE_MATERIAL="",n.uniforms=this.uniforms),n}},dispose:{writable:!0,configurable:!0,value(){let{_depthMaterial:n,_distanceMaterial:a}=this;n&&n.dispose(),a&&a.dispose(),t.dispose.call(this)}}};return o[i]=l,new l}function J(t,{vertexShader:e,fragmentShader:i},o,r){let{vertexDefs:c,vertexMainIntro:l,vertexMainOutro:f,vertexTransform:h,fragmentDefs:n,fragmentMainIntro:a,fragmentMainOutro:p,fragmentColorTransform:m,customRewriter:M,timeUniform:x}=o;if(c=c||"",l=l||"",f=f||"",n=n||"",a=a||"",p=p||"",(h||M)&&(e=_(e)),(m||M)&&(i=i.replace(/^[ \t]*#include <((?:tonemapping|encodings|fog|premultiplied_alpha|dithering)_fragment)>/gm,`
//!BEGIN_POST_CHUNK $1
$&
//!END_POST_CHUNK
`),i=_(i)),M){let u=M({vertexShader:e,fragmentShader:i});e=u.vertexShader,i=u.fragmentShader}if(m){let u=[];i=i.replace(/^\/\/!BEGIN_POST_CHUNK[^]+?^\/\/!END_POST_CHUNK/gm,g=>(u.push(g),"")),p=`${m}
${u.join(`
`)}
${p}`}if(x){let u=`
uniform float ${x};
`;c=u+c,n=u+n}return h&&(e=`vec3 troika_position_${r};
vec3 troika_normal_${r};
vec2 troika_uv_${r};
${e}
`,c=`${c}
void troikaVertexTransform${r}(inout vec3 position, inout vec3 normal, inout vec2 uv) {
  ${h}
}
`,l=`
troika_position_${r} = vec3(position);
troika_normal_${r} = vec3(normal);
troika_uv_${r} = vec2(uv);
troikaVertexTransform${r}(troika_position_${r}, troika_normal_${r}, troika_uv_${r});
${l}
`,e=e.replace(/\b(position|normal|uv)\b/g,(u,g,z,C)=>/\battribute\s+vec[23]\s+$/.test(C.substr(0,z))?g:`troika_${g}_${r}`),t.map&&t.map.channel>0||(e=e.replace(/\bMAP_UV\b/g,`troika_uv_${r}`))),e=y(e,r,c,l,f),i=y(i,r,n,a,p),{vertexShader:e,fragmentShader:i}}function y(t,e,i,o,r){return(o||r||i)&&(t=t.replace(k,`
${i}
void troikaOrigMain${e}() {`),t+=`
void main() {
  ${o}
  troikaOrigMain${e}();
  ${r}
}`),t}function W(t,e){return t==="uniforms"?void 0:typeof e=="function"?e.toString():e}var Y=0,A=new Map;function Z(t){let e=JSON.stringify(t,W),i=A.get(e);return i==null&&A.set(e,i=++Y),i}var q={MeshDepthMaterial:"depth",MeshDistanceMaterial:"distanceRGBA",MeshNormalMaterial:"normal",MeshBasicMaterial:"basic",MeshLambertMaterial:"lambert",MeshPhongMaterial:"phong",MeshToonMaterial:"toon",MeshStandardMaterial:"physical",MeshPhysicalMaterial:"physical",MeshMatcapMaterial:"matcap",LineBasicMaterial:"basic",LineDashedMaterial:"dashed",PointsMaterial:"points",ShadowMaterial:"shadow",SpriteMaterial:"sprite"};function re(t){let e=q[t.type];return e?S[e]:t}function oe(t){let e=/\buniform\s+(int|float|vec[234]|mat[34])\s+([A-Za-z_][\w]*)/g,i=Object.create(null),o;for(;(o=e.exec(t))!==null;)i[o[2]]=o[1];return i}function ae(t,e=new I){return typeof e.invert=="function"?e.copy(t).invert():e.getInverse(t),e}var Q=`
uniform vec3 pointA;
uniform vec3 controlA;
uniform vec3 controlB;
uniform vec3 pointB;
uniform float radius;
varying float bezierT;

vec3 cubicBezier(vec3 p1, vec3 c1, vec3 c2, vec3 p2, float t) {
  float t2 = 1.0 - t;
  float b0 = t2 * t2 * t2;
  float b1 = 3.0 * t * t2 * t2;
  float b2 = 3.0 * t * t * t2;
  float b3 = t * t * t;
  return b0 * p1 + b1 * c1 + b2 * c2 + b3 * p2;
}

vec3 cubicBezierDerivative(vec3 p1, vec3 c1, vec3 c2, vec3 p2, float t) {
  float t2 = 1.0 - t;
  return -3.0 * p1 * t2 * t2 +
    c1 * (3.0 * t2 * t2 - 6.0 * t2 * t) +
    c2 * (6.0 * t2 * t - 3.0 * t * t) +
    3.0 * p2 * t * t;
}
`,X=`
float t = position.y;
bezierT = t;
vec3 bezierCenterPos = cubicBezier(pointA, controlA, controlB, pointB, t);
vec3 bezierDir = normalize(cubicBezierDerivative(pointA, controlA, controlB, pointB, t));

// Make "sideways" always perpendicular to the camera ray; this ensures that any twists
// in the cylinder occur where you won't see them: 
vec3 viewDirection = normalMatrix * vec3(0.0, 0.0, 1.0);
if (bezierDir == viewDirection) {
  bezierDir = normalize(cubicBezierDerivative(pointA, controlA, controlB, pointB, t == 1.0 ? t - 0.0001 : t + 0.0001));
}
vec3 sideways = normalize(cross(bezierDir, viewDirection));
vec3 upish = normalize(cross(sideways, bezierDir));

// Build a matrix for transforming this disc in the cylinder:
mat4 discTx;
discTx[0].xyz = sideways * radius;
discTx[1].xyz = bezierDir * radius;
discTx[2].xyz = upish * radius;
discTx[3].xyz = bezierCenterPos;
discTx[3][3] = 1.0;

// Apply transform, ignoring original y
position = (discTx * vec4(position.x, 0.0, position.z, 1.0)).xyz;
normal = normalize(mat3(discTx) * normal);
`,ee=`
uniform vec3 dashing;
varying float bezierT;
`,te=`
if (dashing.x + dashing.y > 0.0) {
  float dashFrac = mod(bezierT - dashing.z, dashing.x + dashing.y);
  if (dashFrac > dashing.x) {
    discard;
  }
}
`;function ie(t){return D(t,{chained:!0,uniforms:{pointA:{value:new d},controlA:{value:new d},controlB:{value:new d},pointB:{value:new d},radius:{value:.01},dashing:{value:new d}},vertexDefs:Q,vertexTransform:X,fragmentDefs:ee,fragmentMainIntro:te})}var B=null,T=new L({color:16777215,side:j}),$=class t extends N{static getGeometry(){return B||(B=new H(1,1,1,6,64).translate(0,.5,0))}constructor(){super(t.getGeometry(),T),this.pointA=new d,this.controlA=new d,this.controlB=new d,this.pointB=new d,this.radius=.01,this.dashArray=new K,this.dashOffset=0,this.frustumCulled=!1}get material(){let e=this._derivedMaterial,i=this._baseMaterial||this._defaultMaterial||(this._defaultMaterial=T.clone());return(!e||e.baseMaterial!==i)&&(e=this._derivedMaterial=ie(i),i.addEventListener("dispose",function o(){i.removeEventListener("dispose",o),e.dispose()})),e}set material(e){this._baseMaterial=e}get customDepthMaterial(){return this.material.getDepthMaterial()}get customDistanceMaterial(){return this.material.getDistanceMaterial()}onBeforeRender(){let{uniforms:e}=this.material,{pointA:i,controlA:o,controlB:r,pointB:c,radius:l,dashArray:f,dashOffset:h}=this;e.pointA.value.copy(i),e.controlA.value.copy(o),e.controlB.value.copy(r),e.pointB.value.copy(c),e.radius.value=l,e.dashing.value.set(f.x,f.y,h||0)}raycast(){}};export{$ as BezierMesh,D as createDerivedMaterial,_ as expandShaderIncludes,oe as getShaderUniformTypes,re as getShadersForMaterial,ae as invertMatrix4,k as voidMainRegExp};
//# sourceMappingURL=troika-three-utils.mjs.map