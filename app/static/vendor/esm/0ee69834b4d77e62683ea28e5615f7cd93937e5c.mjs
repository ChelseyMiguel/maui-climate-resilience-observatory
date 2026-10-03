/* esm.sh - meshline@3.3.1 */
import*as r from"three";var H=Object.defineProperty,V=(a,t,e)=>t in a?H(a,t,{enumerable:!0,configurable:!0,writable:!0,value:e}):a[t]=e,n=(a,t,e)=>(V(a,typeof t!="symbol"?t+"":t,e),e);function d(a,t,e,i,s){let o;if(a=a.subarray||a.slice?a:a.buffer,e=e.subarray||e.slice?e:e.buffer,a=t?a.subarray?a.subarray(t,s&&t+s):a.slice(t,s&&t+s):a,e.set)e.set(a,i);else for(o=0;o<a.length;o++)e[o+i]=a[o];return e}function C(a){return a instanceof Float32Array?a:a instanceof r.BufferGeometry?a.getAttribute("position").array:a.map(t=>{let e=Array.isArray(t);return t instanceof r.Vector3?[t.x,t.y,t.z]:t instanceof r.Vector2?[t.x,t.y,0]:e&&t.length===3?[t[0],t[1],t[2]]:e&&t.length===2?[t[0],t[1],0]:t}).flat()}var A=class extends r.BufferGeometry{constructor(){super(),n(this,"type","MeshLine"),n(this,"isMeshLine",!0),n(this,"positions",[]),n(this,"previous",[]),n(this,"next",[]),n(this,"side",[]),n(this,"width",[]),n(this,"indices_array",[]),n(this,"uvs",[]),n(this,"counters",[]),n(this,"widthCallback",null),n(this,"_attributes"),n(this,"_points",[]),n(this,"points"),n(this,"matrixWorld",new r.Matrix4),Object.defineProperties(this,{points:{enumerable:!0,get(){return this._points},set(t){this.setPoints(t,this.widthCallback)}}})}setMatrixWorld(t){this.matrixWorld=t}setPoints(t,e){if(t=C(t),this._points=t,this.widthCallback=e??null,this.positions=[],this.counters=[],t.length&&t[0]instanceof r.Vector3)for(let i=0;i<t.length;i++){let s=t[i],o=i/(t.length-1);this.positions.push(s.x,s.y,s.z),this.positions.push(s.x,s.y,s.z),this.counters.push(o),this.counters.push(o)}else for(let i=0;i<t.length;i+=3){let s=i/(t.length-1);this.positions.push(t[i],t[i+1],t[i+2]),this.positions.push(t[i],t[i+1],t[i+2]),this.counters.push(s),this.counters.push(s)}this.process()}compareV3(t,e){let i=t*6,s=e*6;return this.positions[i]===this.positions[s]&&this.positions[i+1]===this.positions[s+1]&&this.positions[i+2]===this.positions[s+2]}copyV3(t){let e=t*6;return[this.positions[e],this.positions[e+1],this.positions[e+2]]}process(){let t=this.positions.length/6;this.previous=[],this.next=[],this.side=[],this.width=[],this.indices_array=[],this.uvs=[];let e,i;this.compareV3(0,t-1)?i=this.copyV3(t-2):i=this.copyV3(0),this.previous.push(i[0],i[1],i[2]),this.previous.push(i[0],i[1],i[2]);for(let s=0;s<t;s++){if(this.side.push(1),this.side.push(-1),this.widthCallback?e=this.widthCallback(s/(t-1)):e=1,this.width.push(e),this.width.push(e),this.uvs.push(s/(t-1),0),this.uvs.push(s/(t-1),1),s<t-1){i=this.copyV3(s),this.previous.push(i[0],i[1],i[2]),this.previous.push(i[0],i[1],i[2]);let o=s*2;this.indices_array.push(o,o+1,o+2),this.indices_array.push(o+2,o+1,o+3)}s>0&&(i=this.copyV3(s),this.next.push(i[0],i[1],i[2]),this.next.push(i[0],i[1],i[2]))}this.compareV3(t-1,0)?i=this.copyV3(1):i=this.copyV3(t-1),this.next.push(i[0],i[1],i[2]),this.next.push(i[0],i[1],i[2]),!this._attributes||this._attributes.position.count!==this.counters.length?this._attributes={position:new r.BufferAttribute(new Float32Array(this.positions),3),previous:new r.BufferAttribute(new Float32Array(this.previous),3),next:new r.BufferAttribute(new Float32Array(this.next),3),side:new r.BufferAttribute(new Float32Array(this.side),1),width:new r.BufferAttribute(new Float32Array(this.width),1),uv:new r.BufferAttribute(new Float32Array(this.uvs),2),index:new r.BufferAttribute(new Uint16Array(this.indices_array),1),counters:new r.BufferAttribute(new Float32Array(this.counters),1)}:(this._attributes.position.copyArray(new Float32Array(this.positions)),this._attributes.position.needsUpdate=!0,this._attributes.previous.copyArray(new Float32Array(this.previous)),this._attributes.previous.needsUpdate=!0,this._attributes.next.copyArray(new Float32Array(this.next)),this._attributes.next.needsUpdate=!0,this._attributes.side.copyArray(new Float32Array(this.side)),this._attributes.side.needsUpdate=!0,this._attributes.width.copyArray(new Float32Array(this.width)),this._attributes.width.needsUpdate=!0,this._attributes.uv.copyArray(new Float32Array(this.uvs)),this._attributes.uv.needsUpdate=!0,this._attributes.index.copyArray(new Uint16Array(this.indices_array)),this._attributes.index.needsUpdate=!0),this.setAttribute("position",this._attributes.position),this.setAttribute("previous",this._attributes.previous),this.setAttribute("next",this._attributes.next),this.setAttribute("side",this._attributes.side),this.setAttribute("width",this._attributes.width),this.setAttribute("uv",this._attributes.uv),this.setAttribute("counters",this._attributes.counters),this.setAttribute("position",this._attributes.position),this.setAttribute("previous",this._attributes.previous),this.setAttribute("next",this._attributes.next),this.setAttribute("side",this._attributes.side),this.setAttribute("width",this._attributes.width),this.setAttribute("uv",this._attributes.uv),this.setAttribute("counters",this._attributes.counters),this.setIndex(this._attributes.index),this.computeBoundingSphere(),this.computeBoundingBox()}advance({x:t,y:e,z:i}){let s=this._attributes.position.array,o=this._attributes.previous.array,h=this._attributes.next.array,u=s.length;d(s,0,o,0,u),d(s,6,s,0,u-6),s[u-6]=t,s[u-5]=e,s[u-4]=i,s[u-3]=t,s[u-2]=e,s[u-1]=i,d(s,6,h,0,u-6),h[u-6]=t,h[u-5]=e,h[u-4]=i,h[u-3]=t,h[u-2]=e,h[u-1]=i,this._attributes.position.needsUpdate=!0,this._attributes.previous.needsUpdate=!0,this._attributes.next.needsUpdate=!0}},U=`
  #include <common>
  #include <logdepthbuf_pars_vertex>
  #include <fog_pars_vertex>
  #include <clipping_planes_pars_vertex>

  attribute vec3 previous;
  attribute vec3 next;
  attribute float side;
  attribute float width;
  attribute float counters;
  
  uniform vec2 resolution;
  uniform float lineWidth;
  uniform vec3 color;
  uniform float opacity;
  uniform float sizeAttenuation;
  
  varying vec2 vUV;
  varying vec4 vColor;
  varying float vCounters;
  
  vec2 fix(vec4 i, float aspect) {
    vec2 res = i.xy / i.w;
    res.x *= aspect;
    return res;
  }
  
  void main() {
    float aspect = resolution.x / resolution.y;
    vColor = vec4(color, opacity);
    vUV = uv;
    vCounters = counters;
  
    mat4 m = projectionMatrix * modelViewMatrix;
    vec4 finalPosition = m * vec4(position, 1.0) * aspect;
    vec4 prevPos = m * vec4(previous, 1.0);
    vec4 nextPos = m * vec4(next, 1.0);
  
    vec2 currentP = fix(finalPosition, aspect);
    vec2 prevP = fix(prevPos, aspect);
    vec2 nextP = fix(nextPos, aspect);
  
    float w = lineWidth * width;
  
    vec2 dir;
    if (nextP == currentP) dir = normalize(currentP - prevP);
    else if (prevP == currentP) dir = normalize(nextP - currentP);
    else {
      vec2 dir1 = normalize(currentP - prevP);
      vec2 dir2 = normalize(nextP - currentP);
      dir = normalize(dir1 + dir2);
  
      vec2 perp = vec2(-dir1.y, dir1.x);
      vec2 miter = vec2(-dir.y, dir.x);
      //w = clamp(w / dot(miter, perp), 0., 4. * lineWidth * width);
    }
  
    //vec2 normal = (cross(vec3(dir, 0.), vec3(0., 0., 1.))).xy;
    vec4 normal = vec4(-dir.y, dir.x, 0., 1.);
    normal.xy *= .5 * w;
    //normal *= projectionMatrix;
    if (sizeAttenuation == 0.) {
      normal.xy *= finalPosition.w;
      normal.xy /= (vec4(resolution, 0., 1.) * projectionMatrix).xy * aspect;
    }
  
    finalPosition.xy += normal.xy * side;
    gl_Position = finalPosition;
    #include <logdepthbuf_vertex>
    #include <fog_vertex>
    vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
    #include <clipping_planes_vertex>
    #include <fog_vertex>
  }
`,W=parseInt(r.REVISION.replace(/\D+/g,"")),F=W>=154?"colorspace_fragment":"encodings_fragment",S=`
  #include <fog_pars_fragment>
  #include <logdepthbuf_pars_fragment>
  #include <clipping_planes_pars_fragment>
  
  uniform sampler2D map;
  uniform sampler2D alphaMap;
  uniform float useGradient;
  uniform float useMap;
  uniform float useAlphaMap;
  uniform float useDash;
  uniform float dashArray;
  uniform float dashOffset;
  uniform float dashRatio;
  uniform float visibility;
  uniform float alphaTest;
  uniform vec2 repeat;
  uniform vec3 gradient[2];
  
  varying vec2 vUV;
  varying vec4 vColor;
  varying float vCounters;
  
  void main() {
    #include <logdepthbuf_fragment>
    vec4 diffuseColor = vColor;
    if (useGradient == 1.) diffuseColor = vec4(mix(gradient[0], gradient[1], vCounters), 1.0);
    if (useMap == 1.) diffuseColor *= texture2D(map, vUV * repeat);
    if (useAlphaMap == 1.) diffuseColor.a *= texture2D(alphaMap, vUV * repeat).a;
    if (diffuseColor.a < alphaTest) discard;
    if (useDash == 1.) diffuseColor.a *= ceil(mod(vCounters + dashOffset, dashArray) - (dashArray * dashRatio));
    diffuseColor.a *= step(vCounters, visibility);
    #include <clipping_planes_fragment>
    gl_FragColor = diffuseColor;     
    #include <fog_fragment>
    #include <tonemapping_fragment>
    #include <${F}>
  }
`,w=class extends r.ShaderMaterial{constructor(t){super({uniforms:{...r.UniformsLib.fog,lineWidth:{value:1},map:{value:null},useMap:{value:0},alphaMap:{value:null},useAlphaMap:{value:0},color:{value:new r.Color(16777215)},gradient:{value:[new r.Color(16711680),new r.Color(65280)]},opacity:{value:1},resolution:{value:new r.Vector2(1,1)},sizeAttenuation:{value:1},dashArray:{value:0},dashOffset:{value:0},dashRatio:{value:.5},useDash:{value:0},useGradient:{value:0},visibility:{value:1},alphaTest:{value:0},repeat:{value:new r.Vector2(1,1)}},vertexShader:U,fragmentShader:S}),n(this,"lineWidth"),n(this,"map"),n(this,"useMap"),n(this,"alphaMap"),n(this,"useAlphaMap"),n(this,"color"),n(this,"gradient"),n(this,"resolution"),n(this,"sizeAttenuation"),n(this,"dashArray"),n(this,"dashOffset"),n(this,"dashRatio"),n(this,"useDash"),n(this,"useGradient"),n(this,"visibility"),n(this,"repeat"),this.type="MeshLineMaterial",Object.defineProperties(this,{lineWidth:{enumerable:!0,get(){return this.uniforms.lineWidth.value},set(e){this.uniforms.lineWidth.value=e}},map:{enumerable:!0,get(){return this.uniforms.map.value},set(e){this.uniforms.map.value=e}},useMap:{enumerable:!0,get(){return this.uniforms.useMap.value},set(e){this.uniforms.useMap.value=e}},alphaMap:{enumerable:!0,get(){return this.uniforms.alphaMap.value},set(e){this.uniforms.alphaMap.value=e}},useAlphaMap:{enumerable:!0,get(){return this.uniforms.useAlphaMap.value},set(e){this.uniforms.useAlphaMap.value=e}},color:{enumerable:!0,get(){return this.uniforms.color.value},set(e){this.uniforms.color.value=e}},gradient:{enumerable:!0,get(){return this.uniforms.gradient.value},set(e){this.uniforms.gradient.value=e}},opacity:{enumerable:!0,get(){return this.uniforms.opacity.value},set(e){this.uniforms.opacity.value=e}},resolution:{enumerable:!0,get(){return this.uniforms.resolution.value},set(e){this.uniforms.resolution.value.copy(e)}},sizeAttenuation:{enumerable:!0,get(){return this.uniforms.sizeAttenuation.value},set(e){this.uniforms.sizeAttenuation.value=e}},dashArray:{enumerable:!0,get(){return this.uniforms.dashArray.value},set(e){this.uniforms.dashArray.value=e,this.useDash=e!==0?1:0}},dashOffset:{enumerable:!0,get(){return this.uniforms.dashOffset.value},set(e){this.uniforms.dashOffset.value=e}},dashRatio:{enumerable:!0,get(){return this.uniforms.dashRatio.value},set(e){this.uniforms.dashRatio.value=e}},useDash:{enumerable:!0,get(){return this.uniforms.useDash.value},set(e){this.uniforms.useDash.value=e}},useGradient:{enumerable:!0,get(){return this.uniforms.useGradient.value},set(e){this.uniforms.useGradient.value=e}},visibility:{enumerable:!0,get(){return this.uniforms.visibility.value},set(e){this.uniforms.visibility.value=e}},alphaTest:{enumerable:!0,get(){return this.uniforms.alphaTest.value},set(e){this.uniforms.alphaTest.value=e}},repeat:{enumerable:!0,get(){return this.uniforms.repeat.value},set(e){this.uniforms.repeat.value.copy(e)}}}),this.setValues(t)}copy(t){return super.copy(t),this.lineWidth=t.lineWidth,this.map=t.map,this.useMap=t.useMap,this.alphaMap=t.alphaMap,this.useAlphaMap=t.useAlphaMap,this.color.copy(t.color),this.gradient=t.gradient,this.opacity=t.opacity,this.resolution.copy(t.resolution),this.sizeAttenuation=t.sizeAttenuation,this.dashArray=t.dashArray,this.dashOffset=t.dashOffset,this.dashRatio=t.dashRatio,this.useDash=t.useDash,this.useGradient=t.useGradient,this.visibility=t.visibility,this.alphaTest=t.alphaTest,this.repeat.copy(t.repeat),this}};function z(a,t){let e=new r.Matrix4,i=new r.Ray,s=new r.Sphere,o=new r.Vector3,h=this.geometry;if(s.copy(h.boundingSphere),s.applyMatrix4(this.matrixWorld),!a.ray.intersectSphere(s,o))return;e.copy(this.matrixWorld).invert(),i.copy(a.ray).applyMatrix4(e);let u=new r.Vector3,f=new r.Vector3,v=new r.Vector3,E=this instanceof r.LineSegments?2:1,m=h.index,y=h.attributes;if(m!==null){let p=m.array,b=y.position.array,x=y.width.array;for(let l=0,g=p.length-1;l<g;l+=E){let M=p[l],R=p[l+1];u.fromArray(b,M*3),f.fromArray(b,R*3);let T=x[Math.floor(l/3)]!=null?x[Math.floor(l/3)]:1,_=a.params.Line.threshold+this.material.lineWidth*T/2,P=_*_;if(i.distanceSqToSegment(u,f,o,v)>P)continue;o.applyMatrix4(this.matrixWorld);let c=a.ray.origin.distanceTo(o);c<a.near||c>a.far||(t.push({distance:c,point:v.clone().applyMatrix4(this.matrixWorld),index:l,face:null,faceIndex:void 0,object:this}),l=g)}}}export{A as MeshLineGeometry,w as MeshLineMaterial,z as raycast};
//# sourceMappingURL=meshline.mjs.map