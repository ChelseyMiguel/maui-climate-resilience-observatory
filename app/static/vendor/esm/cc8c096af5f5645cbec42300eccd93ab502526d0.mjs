/* esm.sh - zustand@3.7.2/shallow */
function n(t,e){if(Object.is(t,e))return!0;if(typeof t!="object"||t===null||typeof e!="object"||e===null)return!1;let r=Object.keys(t);if(r.length!==Object.keys(e).length)return!1;for(let l=0;l<r.length;l++)if(!Object.prototype.hasOwnProperty.call(e,r[l])||!Object.is(t[r[l]],e[r[l]]))return!1;return!0}export{n as default};
//# sourceMappingURL=shallow.mjs.map