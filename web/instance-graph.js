/* instance-graph.js — 本体实例数据 SVG 层级大图(企业居中, 双向滚动)
   层级布局: 企业中心 → 产品/类别内环 → 供应链/库存/销售中环 → 客户/设备外环
   数据: /graph/full; 换数据自动重新建模 → 新大图 → 新检索关系 */
const GRAPH_COLORS = {Product:"#2f6bff",Supplier:"#27ae60",Inventory:"#f39c12",Sale:"#e74c3c",Customer:"#8e44ad",Equipment:"#16a085",Category:"#95a5a6"};

async function loadGraphFull(){
  const el=document.getElementById('ontology-graph');
  let r;
  try{ r=await api('/graph/full'); }catch(e){ el.innerHTML='<div class="empty">实例图加载失败</div>';return; }
  if(!r.ok||!r.nodes||!r.nodes.length){ el.innerHTML='<div class="empty">无实例数据</div>';return; }
  const nodes=r.nodes, edges=r.edges||[];
  // 层级布局: 大画布 1400x900, 企业/产品为中心, 各实体按环层分布(非力导向平铺)
  const W=1400,H=900,cx=W/2,cy=H/2;
  const ring={Category:50,Product:130,Supplier:230,Inventory:230,Sale:330,Equipment:330,Customer:430};
  const pos={}, grp={};
  nodes.forEach(n=>{ (grp[n.entity]=grp[n.entity]||[]).push(n); });
  Object.keys(grp).forEach(et=>{
    const arr=grp[et], r=ring[et]||200, k=arr.length;
    arr.forEach((n,i)=>{ const ang=2*Math.PI*i/k; pos[n.id]={x:cx+Math.cos(ang)*r, y:cy+Math.sin(ang)*r}; });
  });
  // 企业中心节点(核心始终可见)
  pos['__hub__']={x:cx,y:cy};
  // 企业 → 类别/产品 中心连接线(让"企业为中心"清晰)
  const centerLinks=(grp['Category']||[]).concat(grp['Product']||[]).slice(0,8);
  // 渲染 SVG(大画布, 容器 overflow:auto 可上下左右拖动)
  let svg=`<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">`;
  // 中心辐射线(企业 → 产品/类别)
  centerLinks.forEach(n=>{ const p=pos[n.id]; svg+=`<line x1="${cx}" y1="${cy}" x2="${p.x}" y2="${p.y}" stroke="#2f6bff" stroke-width="1" opacity=".25"/>`; });
  // 关系边
  edges.forEach(e=>{
    const a=pos[e.from],b=pos[e.to]; if(!a||!b)return;
    svg+=`<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" stroke="#d6e4ff" stroke-width="1"/>`;
  });
  // 企业中心节点
  svg+=`<g><circle cx="${cx}" cy="${cy}" r="36" fill="#2f6bff" stroke="#fff" stroke-width="2"/>
    <text x="${cx}" y="${cy+4}" font-size="18" font-weight="700" fill="#fff" text-anchor="middle">企业</text></g>`;
  // 实体实例节点
  nodes.forEach(n=>{
    const p=pos[n.id],c=GRAPH_COLORS[n.entity]||"#95a5a6";
    const rr=n.entity==='Category'?12:8;
    svg+=`<g><circle cx="${p.x}" cy="${p.y}" r="${rr}" fill="${c}" opacity=".88"/>
    <text x="${p.x}" y="${p.y-rr-6}" font-size="${n.entity==='Category'?12:9}" fill="#1a2233" text-anchor="middle">${esc(n.name||n.id_val)}</text></g>`;
  });
  svg+=`</svg>`;
  // 图例
  const legend=Object.entries(GRAPH_COLORS).map(([k,v])=>`<span style="display:inline-block;margin-right:12px;font-size:11px;color:var(--dim)"><i style="display:inline-block;width:9px;height:9px;border-radius:50%;background:${v};margin-right:4px"></i>${k}</span>`).join('');
  el.innerHTML=`<div class="graph-scroll">${svg}</div>
    <div style="padding:8px 2px;font-size:11px;color:var(--dim)">${nodes.length} 节点 · ${edges.length} 边 · 左右上下拖动滚动条看全图 · 企业为中心 · 换数据自动重新建模生成新大图新检索关系</div>
    <div style="padding:4px 2px">${legend}</div>`;
}
