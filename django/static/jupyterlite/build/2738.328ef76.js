"use strict";(self.webpackChunk_JUPYTERLAB_CORE_OUTPUT=self.webpackChunk_JUPYTERLAB_CORE_OUTPUT||[]).push([[2738],{86798:(e,t,n)=>{n.r(t),n.d(t,{main:()=>l});var s=n(65021),i=n(12439);n(5053);const o=[n.e(9195).then(n.t.bind(n,49195,23)),n.e(2045).then(n.t.bind(n,52045,23)),n.e(5258).then(n.t.bind(n,15258,23))],r=[n.e(395).then(n.t.bind(n,80395,23)),n.e(5434).then(n.t.bind(n,15434,23)),n.e(354).then(n.t.bind(n,70354,23)),n.e(4638).then(n.t.bind(n,44638,23))];async function a(e,t){try{return(await window._JUPYTERLAB[e].get(t))()}catch(n){throw console.warn(`Failed to create module: package: ${e}; module: ${t}`),n}}async function l(){const e=await Promise.all(r);let t=[n(3901),n(61868),n(88394).default.filter((({id:e})=>!["@retrolab/application-extension:logo","@retrolab/application-extension:opener"].includes(e))),n(31161),n(61474),n(75203).default.filter((({id:e})=>["@jupyterlab/application-extension:commands","@jupyterlab/application-extension:context-menu","@jupyterlab/application-extension:faviconbusy"].includes(e))),n(72793).default.filter((({id:e})=>["@jupyterlab/apputils-extension:palette","@jupyterlab/apputils-extension:settings","@jupyterlab/apputils-extension:state","@jupyterlab/apputils-extension:themes","@jupyterlab/apputils-extension:themes-palette-menu","@jupyterlab/apputils-extension:toolbar-registry"].includes(e))),n(76637).default.filter((({id:e})=>["@jupyterlab/codemirror-extension:services","@jupyterlab/codemirror-extension:codemirror"].includes(e))),n(68638).default.filter((({id:e})=>["@jupyterlab/completer-extension:manager"].includes(e))),n(63002),n(81070).default.filter((({id:e})=>["@jupyterlab/docmanager-extension:plugin","@jupyterlab/docmanager-extension:manager"].includes(e))),n(3098).default.filter((({id:e})=>["@jupyterlab/filebrowser-extension:factory"].includes(e))),n(78032),n(92651),n(71623).default.filter((({id:e})=>["@jupyterlab/notebook-extension:factory","@jupyterlab/notebook-extension:tracker","@jupyterlab/notebook-extension:widget-factory"].includes(e))),n(10156),n(24684),n(93478),n(38899),n(63814)];switch(i.PageConfig.getOption("retroPage")){case"tree":t=t.concat([n(3098).default.filter((({id:e})=>["@jupyterlab/filebrowser-extension:browser","@jupyterlab/filebrowser-extension:file-upload-status","@jupyterlab/filebrowser-extension:open-with"].includes(e))),n(24918).default.filter((({id:e})=>"@retrolab/tree-extension:new-terminal"!==e))]);break;case"notebooks":t=t.concat([n(30671),n(68638).default.filter((({id:e})=>["@jupyterlab/completer-extension:notebooks"].includes(e))),n(98844).default.filter((({id:e})=>["@jupyterlab/tooltip-extension:manager","@jupyterlab/tooltip-extension:notebooks"].includes(e)))]);break;case"consoles":t=t.concat([n(68638).default.filter((({id:e})=>["@jupyterlab/completer-extension:consoles"].includes(e))),n(98844).default.filter((({id:e})=>["@jupyterlab/tooltip-extension:manager","@jupyterlab/tooltip-extension:consoles"].includes(e)))]);break;case"edit":t=t.concat([n(68638).default.filter((({id:e})=>["@jupyterlab/completer-extension:files"].includes(e))),n(68648).default.filter((({id:e})=>["@jupyterlab/fileeditor-extension:plugin"].includes(e))),n(3098).default.filter((({id:e})=>["@jupyterlab/filebrowser-extension:browser"].includes(e)))])}const l=[],A=[],d=[],c=[],p=[],u=[],f=JSON.parse(i.PageConfig.getOption("federated_extensions")),m=new Set;function*g(e){let t;t=e.hasOwnProperty("__esModule")?e.default:e;let n=Array.isArray(t)?t:[t];for(let e of n)i.PageConfig.Extension.isDisabled(e.id)||(yield e)}f.forEach((e=>{e.liteExtension?u.push(a(e.name,e.extension)):(e.extension&&(m.add(e.name),A.push(a(e.name,e.extension))),e.mimeExtension&&(m.add(e.name),d.push(a(e.name,e.mimeExtension))),e.style&&c.push(a(e.name,e.style)))})),(await Promise.all(t)).forEach((e=>{for(let t of g(e))l.push(t)})),(await Promise.allSettled(d)).forEach((t=>{if("fulfilled"===t.status)for(let n of g(t.value))e.push(n);else console.error(t.reason)})),(await Promise.allSettled(A)).forEach((e=>{if("fulfilled"===e.status)for(let t of g(e.value))l.push(t);else console.error(e.reason)})),(await Promise.all(o)).forEach((e=>{for(let t of g(e))p.push(t)})),(await Promise.allSettled(u)).forEach((e=>{if("fulfilled"===e.status)for(let t of g(e.value))p.push(t);else console.error(e.reason)}));const b=new s.JupyterLiteServer({});b.registerPluginModules(p),await b.start();const{serviceManager:h}=b,{RetroApp:y}=n(95191),w=new y({serviceManager:h,mimeExtensions:e});w.name=i.PageConfig.getOption("appName")||"RetroLite",w.registerPluginModules(l),"true"===(i.PageConfig.getOption("exposeAppInBrowser")||"").toLowerCase()&&(window.jupyterapp=w),await w.start(),await w.restored}},5053:(e,t,n)=>{n.r(t),n(94101),n(94395),n(48808),n(18934),n(19422),n(72867),n(91532),n(17363),n(9755),n(76838),n(53109),n(3727),n(86304),n(84221),n(87967),n(63897),n(16388),n(37609),n(74958),n(58169);var s=n(1892),i=n.n(s),o=n(95760),r=n.n(o),a=n(38311),l=n.n(a),A=n(58192),d=n.n(A),c=n(38060),p=n.n(c),u=n(54865),f=n.n(u),m=n(12563),g={};g.styleTagTransform=f(),g.setAttributes=d(),g.insert=l().bind(null,"head"),g.domAPI=r(),g.insertStyleElement=p(),i()(m.Z,g),m.Z&&m.Z.locals&&m.Z.locals,n(94453);var b=n(59988),h={};h.styleTagTransform=f(),h.setAttributes=d(),h.insert=l().bind(null,"head"),h.domAPI=r(),h.insertStyleElement=p(),i()(b.Z,h),b.Z&&b.Z.locals&&b.Z.locals;var y=n(76632),w={};w.styleTagTransform=f(),w.setAttributes=d(),w.insert=l().bind(null,"head"),w.domAPI=r(),w.insertStyleElement=p(),i()(y.Z,w),y.Z&&y.Z.locals&&y.Z.locals;var x=n(228),v={};v.styleTagTransform=f(),v.setAttributes=d(),v.insert=l().bind(null,"head"),v.domAPI=r(),v.insertStyleElement=p(),i()(x.Z,v),x.Z&&x.Z.locals&&x.Z.locals;var E=n(94298),C={};C.styleTagTransform=f(),C.setAttributes=d(),C.insert=l().bind(null,"head"),C.domAPI=r(),C.insertStyleElement=p(),i()(E.Z,C),E.Z&&E.Z.locals&&E.Z.locals,n(49206),n(3231),n(80448),n(41762),n(94328)},12563:(e,t,n)=>{n.d(t,{Z:()=>a});var s=n(20559),i=n.n(s),o=n(93476),r=n.n(o)()(i());r.push([e.id,"/*-----------------------------------------------------------------------------\n| Copyright (c) Jupyter Development Team.\n| Distributed under the terms of the Modified BSD License.\n|----------------------------------------------------------------------------*/\n","",{version:3,sources:["webpack://./../packages/application-extension/style/base.css"],names:[],mappings:"AAAA;;;8EAG8E",sourcesContent:["/*-----------------------------------------------------------------------------\n| Copyright (c) Jupyter Development Team.\n| Distributed under the terms of the Modified BSD License.\n|----------------------------------------------------------------------------*/\n"],sourceRoot:""}]);const a=r},59988:(e,t,n)=>{n.d(t,{Z:()=>a});var s=n(20559),i=n.n(s),o=n(93476),r=n.n(o)()(i());r.push([e.id,"/*-----------------------------------------------------------------------------\n| Copyright (c) Jupyter Development Team.\n| Distributed under the terms of the Modified BSD License.\n|----------------------------------------------------------------------------*/\n\n.jp-IFrameContainer iframe,\n.jp-IFrameContainer body {\n  margin: 0;\n  padding: 0;\n  overflow: hidden;\n  border: none;\n}\n","",{version:3,sources:["webpack://./../packages/iframe-extension/style/base.css"],names:[],mappings:"AAAA;;;8EAG8E;;AAE9E;;EAEE,SAAS;EACT,UAAU;EACV,gBAAgB;EAChB,YAAY;AACd",sourcesContent:["/*-----------------------------------------------------------------------------\n| Copyright (c) Jupyter Development Team.\n| Distributed under the terms of the Modified BSD License.\n|----------------------------------------------------------------------------*/\n\n.jp-IFrameContainer iframe,\n.jp-IFrameContainer body {\n  margin: 0;\n  padding: 0;\n  overflow: hidden;\n  border: none;\n}\n"],sourceRoot:""}]);const a=r},76632:(e,t,n)=>{n.d(t,{Z:()=>a});var s=n(20559),i=n.n(s),o=n(93476),r=n.n(o)()(i());r.push([e.id,"/*-----------------------------------------------------------------------------\n| Copyright (c) Jupyter Development Team.\n| Distributed under the terms of the Modified BSD License.\n|----------------------------------------------------------------------------*/\n","",{version:3,sources:["webpack://./../packages/javascript-kernel-extension/style/base.css"],names:[],mappings:"AAAA;;;8EAG8E",sourcesContent:["/*-----------------------------------------------------------------------------\n| Copyright (c) Jupyter Development Team.\n| Distributed under the terms of the Modified BSD License.\n|----------------------------------------------------------------------------*/\n"],sourceRoot:""}]);const a=r},228:(e,t,n)=>{n.d(t,{Z:()=>a});var s=n(20559),i=n.n(s),o=n(93476),r=n.n(o)()(i());r.push([e.id,"/*-----------------------------------------------------------------------------\n| Copyright (c) Jupyter Development Team.\n| Distributed under the terms of the Modified BSD License.\n|----------------------------------------------------------------------------*/\n","",{version:3,sources:["webpack://./../packages/retro-application-extension/style/base.css"],names:[],mappings:"AAAA;;;8EAG8E",sourcesContent:["/*-----------------------------------------------------------------------------\n| Copyright (c) Jupyter Development Team.\n| Distributed under the terms of the Modified BSD License.\n|----------------------------------------------------------------------------*/\n"],sourceRoot:""}]);const a=r},94298:(e,t,n)=>{n.d(t,{Z:()=>a});var s=n(20559),i=n.n(s),o=n(93476),r=n.n(o)()(i());r.push([e.id,"/*-----------------------------------------------------------------------------\n| Copyright (c) Jupyter Development Team.\n| Distributed under the terms of the Modified BSD License.\n|----------------------------------------------------------------------------*/\n","",{version:3,sources:["webpack://./../packages/server-extension/style/base.css"],names:[],mappings:"AAAA;;;8EAG8E",sourcesContent:["/*-----------------------------------------------------------------------------\n| Copyright (c) Jupyter Development Team.\n| Distributed under the terms of the Modified BSD License.\n|----------------------------------------------------------------------------*/\n"],sourceRoot:""}]);const a=r},7413:e=>{e.exports="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAFCAYAAAB4ka1VAAAAsElEQVQIHQGlAFr/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA7+r3zKmT0/+pk9P/7+r3zAAAAAAAAAAABAAAAAAAAAAA6OPzM+/q9wAAAAAA6OPzMwAAAAAAAAAAAgAAAAAAAAAAGR8NiRQaCgAZIA0AGR8NiQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQyoYJ/SY80UAAAAASUVORK5CYII="},6196:e=>{e.exports="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADAAAAAMCAYAAAAkuj5RAAAAAXNSR0IArs4c6QAAAGFJREFUSMft1LsRQFAQheHPowAKoACx3IgEKtaEHujDjORSgWTH/ZOdnZOcM/sgk/kFFWY0qV8foQwS4MKBCS3qR6ixBJvElOobYAtivseIE120FaowJPN75GMu8j/LfMwNjh4HUpwg4LUAAAAASUVORK5CYII="},65767:e=>{e.exports="data:image/svg+xml,%3csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 16 16%27%3e%3cg fill=%27%235C7080%27%3e%3ccircle cx=%272%27 cy=%278.03%27 r=%272%27/%3e%3ccircle cx=%2714%27 cy=%278.03%27 r=%272%27/%3e%3ccircle cx=%278%27 cy=%278.03%27 r=%272%27/%3e%3c/g%3e%3c/svg%3e"},91116:e=>{e.exports="data:image/svg+xml,%3csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 16 16%27%3e%3cpath fill-rule=%27evenodd%27 clip-rule=%27evenodd%27 d=%27M10.71 7.29l-4-4a1.003 1.003 0 00-1.42 1.42L8.59 8 5.3 11.29c-.19.18-.3.43-.3.71a1.003 1.003 0 001.71.71l4-4c.18-.18.29-.43.29-.71 0-.28-.11-.53-.29-.71z%27 fill=%27%235C7080%27/%3e%3c/svg%3e"},83678:e=>{e.exports="data:image/svg+xml,%3csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 16 16%27%3e%3cpath fill-rule=%27evenodd%27 clip-rule=%27evenodd%27 d=%27M11 7H5c-.55 0-1 .45-1 1s.45 1 1 1h6c.55 0 1-.45 1-1s-.45-1-1-1z%27 fill=%27white%27/%3e%3c/svg%3e"},79080:e=>{e.exports="data:image/svg+xml,%3csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 16 16%27%3e%3cpath fill-rule=%27evenodd%27 clip-rule=%27evenodd%27 d=%27M12 5c-.28 0-.53.11-.71.29L7 9.59l-2.29-2.3a1.003 1.003 0 00-1.42 1.42l3 3c.18.18.43.29.71.29s.53-.11.71-.29l5-5A1.003 1.003 0 0012 5z%27 fill=%27white%27/%3e%3c/svg%3e"}}]);
//# sourceMappingURL=2738.328ef76.js.map