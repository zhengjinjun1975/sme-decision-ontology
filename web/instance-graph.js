/* instance-graph.js — 企业级本体大图(常规本体层级: 企业→业务域→实体类→实例, 双向滚动)
   布局: 企业顶部中心 → 业务域列(采购/生产/库存/销售/财务) → 各域实体类 → 实例
   数据: /graph/full; 换数据自动重新建模 → 新大图 → 新检索关系 */
const GRAPH_COLORS = {Product:"#2f6bff",Supplier:"#27ae60",Inventory:"#f39c12",Sale:"#e74c3c",Customer:"#8e44ad",Equipment:"#16a085",Category:"#95a5a6",Purchase:"#e67e22",Production:"#1abc9c",Payment:"#c0392b"};

// 业务域分组(常规企业本体: 上层本体 → 域本体 → 类 → 实例)
const DOMAINS = [
  {name:"采购域", flow:"采购", entities:["Supplier","Purchase"]},
  {name:"生产域", flow:"生产", entities:["Equipment","Production"]},
  {name:"库存域", flow:"库存", entities:["Inventory"]},
  {name:"销售域", flow:"销售", entities:["Category","Product","Sale","Customer"]},
  {name:"财务域", flow:"回款", entities:["Payment"]}
];

async function loadGraphFull(){
  const el=document.getElementById('ontology-graph');
  let r;
  try{ r=await api('/graph/full'); }catch(e){ el.innerHTML='<div class="empty">实例图加载失败</div>';return; }
  if(!r.ok||!r.nodes||!r.nodes.length){ el.innerHTML='<div class="empty">无实例数据</div>';return; }
  const nodes=r.nodes, edges=r.edges||[];
  // 层级布局: 企业顶部中心, 业务域列, 域内实体类, 实例
  const W=1560,H=980, colW=300, topY=70, cx=W/2;
  const pos={}, grp={};
  nodes.forEach(n=>{ (grp[n.entity]=grp[n.entity]||[]).push(n); });
  // 企业(顶层本体)顶部中心
  pos['__hub__']={x:cx,y:topY};
  // 业务域列: 每个域一列, 域内实体类从上往下, 实例在类下方
  const startX=100, gap=280;
  const domainY={};
  DOMAINS.forEach((d,di)=>{
    const dx=startX+di*gap;
    domainY[d.name]=topY+80;
    let y=topY+110;  // 域内起始y
    d.entities.forEach(et=>{
      const arr=grp[et]||[];
      // 实体类标签
      pos['__cls__'+et]={x:dx+colW/2, y:y};
      y+=34;
      // 实例纵向排列
      arr.forEach((n,i)=>{
        const col=(i%6); // 每行最多6个, 换行横向
        const yy=y+Math.floor(i/6)*44;
        pos[n.id]={x:dx+40+col*44, y:yy};
      });
      if(arr.length) y+=Math.ceil(arr.length/6)*44+40;
    });
  });
  // 渲染 SVG(大画布, 容器强制滚动)
  let svg=`<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">`;
  // 企业 → 业务域 连线(上层本体到域本体)
  DOMAINS.forEach(d=>{
    const p=pos['__cls__'+d.entities[0]];
    if(p) svg+=`<line x1="${cx}" y1="${topY+36}" x2="${p.x}" y2="${p.y-20}" stroke="#2f6bff" stroke-width="1.4" opacity=".3"/>`;
  });
  // 关系边(实例间)
  edges.forEach(e=>{
    const a=pos[e.from],b=pos[e.to]; if(!a||!b)return;
    svg+=`<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" stroke="#d6e4ff" stroke-width="1"/>`;
  });
  // 企业顶层节点
  svg+=`<g><circle cx="${cx}" cy="${topY}" r="34" fill="#2f6bff" stroke="#fff" stroke-width="2"/>
    <text x="${cx}" y="${topY+5}" font-size="18" font-weight="700" fill="#fff" text-anchor="middle">企业</text>
    <text x="${cx}" y="${topY+21}" font-size="9" fill="#fff" text-anchor="middle">${nodes.length}实例</text></g>`;
  // 业务域列背景+标签
  DOMAINS.forEach(d=>{
    const dx=startX+DOMAINS.indexOf(d)*gap;
    svg+=`<g><rect x="${dx}" y="${domainY[d.name]}" width="${colW}" height="${H-domainY[d.name]-20}" rx="12" fill="#f0f4ff" stroke="#d6e4ff" stroke-width="1" opacity=".6"/>
    <text x="${dx+colW/2}" y="${domainY[d.name]+18}" font-size="13" font-weight="700" fill="#2f6bff" text-anchor="middle">${d.name}(${d.flow})</text></g>`;
  });
  // 实体类标签 + 实例
  Object.keys(grp).forEach(et=>{
    const cp=pos['__cls__'+et]; if(!cp)return;
    svg+=`<text x="${cp.x}" y="${cp.y+4}" font-size="12" font-weight="600" fill="${GRAPH_COLORS[et]}" text-anchor="middle">${et}(${grp[et].length})</text>`;
  });
  nodes.forEach(n=>{
    const p=pos[n.id],c=GRAPH_COLORS[n.entity]||"#95a5a6";
    svg+=`<g><circle cx="${p.x}" cy="${p.y}" r="7" fill="${c}" opacity=".88">
    <title>${esc(n.entity)} ${esc(n.name||n.id_val)}</title></g>
    <text x="${p.x}" y="${p.y-10}" font-size="8" fill="#1a2233" text-anchor="middle">${esc((n.name||n.id_val).toString().slice(0,10))}</text></g>`;
  });
  svg+=`</svg>`;
  // 图例
  const legend=Object.entries(GRAPH_COLORS).map(([k,v])=>`<span style="display:inline-block;margin-right:12px;font-size:11px;color:var(--dim)"><i style="display:inline-block;width:9px;height:9px;border-radius:50%;background:${v};margin-right:4px"></i>${k}</span>`).join('');
  el.innerHTML=`<div class="graph-scroll">${svg}</div>
    <div style="padding:8px 2px;font-size:11px;color:var(--dim)">${nodes.length} 实例节点 · ${edges.length} 关系边 · 常规本体层级(企业→业务域→实体类→实例) · 左右上下拖动看全图 · 换数据自动重建</div>
    <div style="padding:4px 2px">${legend}</div>`;
}
