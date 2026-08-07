/* instance-graph.js — 企业级本体大图(动态化: 从schema/数据构建业务域列, 跨行业泛化)
   布局: 企业顶部中心 → 业务域列(动态) → 实体类 → 实例
   数据: /graph/full 含 domains + 每节点 domain; 换数据/换行业自动重建新本体新域列 */
const GRAPH_COLORS = {Product:"#2f6bff",Supplier:"#27ae60",Inventory:"#f39c12",Sale:"#e74c3c",Customer:"#8e44ad",Equipment:"#16a085",Category:"#95a5a6",Purchase:"#e67e22",Production:"#1abc9c",Payment:"#c0392b"};
const PALETTE = ["#2f6bff","#27ae60","#f39c12","#e74c3c","#8e44ad","#16a085","#e67e22","#1abc9c","#c0392b","#7f8c8d","#3498db","#d35400"];

async function loadGraphFull(){
  const el=document.getElementById('ontology-graph');
  let r;
  try{ r=await api('/graph/full'); }catch(e){ el.innerHTML='<div class="empty">实例图加载失败</div>';return; }
  if(!r.ok||!r.nodes||!r.nodes.length){ el.innerHTML='<div class="empty">无实例数据</div>';return; }
  const nodes=r.nodes, edges=r.edges||[];
  const domains=r.domains||["其他域"];
  // 动态构建业务域: 每域一列(域来自 schema 的 domain, 跨行业自适应)
  const W=1560,H=980, colW=300, topY=70, cx=W/2;
  const pos={}, grp={};
  nodes.forEach(n=>{ (grp[n.entity]=grp[n.entity]||[]).push(n); });
  const entityDomain={}; nodes.forEach(n=>{ entityDomain[n.entity]=n.domain||"其他域"; });
  pos['__hub__']={x:cx,y:topY};
  // 域 → 列 x 位置
  const startX=100, gap=280;
  const domainX={}; domains.forEach((d,di)=>{ domainX[d]=startX+di*gap; });
  const domainY={};
  domains.forEach(d=>{ domainY[d]=topY+80; });
  // 每域内实体从上往下排, 实例在类下方
  Object.keys(entityDomain).forEach(et=>{
    const d=entityDomain[et], dx=domainX[d];
    let y=topY+110;
    pos['__cls__'+et]={x:dx+colW/2, y:y};
    y+=34;
    const arr=grp[et]||[];
    arr.forEach((n,i)=>{
      const col=(i%6);
      const yy=y+Math.floor(i/6)*44;
      pos[n.id]={x:dx+40+col*44, y:yy};
    });
  });
  // 渲染 SVG(大画布, 容器强制滚动)
  let svg=`<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">`;
  // 企业 → 各域首实体 连线
  domains.forEach(d=>{
    const firstEt=Object.keys(entityDomain).find(et=>entityDomain[et]===d);
    const p=firstEt?pos['__cls__'+firstEt]:null;
    if(p) svg+=`<line x1="${cx}" y1="${topY+36}" x2="${p.x}" y2="${p.y-20}" stroke="#2f6bff" stroke-width="1.4" opacity=".3"/>`;
  });
  // 关系边
  edges.forEach(e=>{
    const a=pos[e.from],b=pos[e.to]; if(!a||!b)return;
    svg+=`<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" stroke="#d6e4ff" stroke-width="1"/>`;
  });
  // 企业顶层节点
  svg+=`<g><circle cx="${cx}" cy="${topY}" r="34" fill="#2f6bff" stroke="#fff" stroke-width="2"/>
    <text x="${cx}" y="${topY+5}" font-size="18" font-weight="700" fill="#fff" text-anchor="middle">企业</text>
    <text x="${cx}" y="${topY+21}" font-size="9" fill="#fff" text-anchor="middle">${nodes.length}实例</text></g>`;
  // 业务域列背景(动态)
  domains.forEach((d,di)=>{
    const dx=domainX[d], col=PALETTE[di%PALETTE.length];
    svg+=`<g><rect x="${dx}" y="${domainY[d]}" width="${colW}" height="${H-domainY[d]-20}" rx="12" fill="${col}18" stroke="${col}44" stroke-width="1" opacity=".7"/>
    <text x="${dx+colW/2}" y="${domainY[d]+18}" font-size="13" font-weight="700" fill="${col}" text-anchor="middle">${esc(d)}</text></g>`;
  });
  // 实体类标签 + 实例
  Object.keys(grp).forEach(et=>{
    const cp=pos['__cls__'+et]; if(!cp)return;
    const col=GRAPH_COLORS[et]||"#7f8c8d";
    svg+=`<text x="${cp.x}" y="${cp.y+4}" font-size="12" font-weight="600" fill="${col}" text-anchor="middle">${et}(${grp[et].length})</text>`;
  });
  nodes.forEach(n=>{
    const p=pos[n.id],c=GRAPH_COLORS[n.entity]||"#7f8c8d";
    svg+=`<g><circle cx="${p.x}" cy="${p.y}" r="7" fill="${c}" opacity=".88">
    <title>${esc(n.entity)} ${esc(n.name||n.id_val)} · ${esc(n.domain||'')}</title></g>
    <text x="${p.x}" y="${p.y-10}" font-size="8" fill="#1a2233" text-anchor="middle">${esc((n.name||n.id_val).toString().slice(0,10))}</text></g>`;
  });
  svg+=`</svg>`;
  // 图例(动态: 用实际出现的实体类型)
  const presentEntities=Object.keys(grp);
  const legend=presentEntities.map(et=>`<span style="display:inline-block;margin-right:12px;font-size:11px;color:var(--dim)"><i style="display:inline-block;width:9px;height:9px;border-radius:50%;background:${GRAPH_COLORS[et]||"#7f8c8d"};margin-right:4px"></i>${et}</span>`).join('');
  el.innerHTML=`<div class="graph-scroll">${svg}</div>
    <div style="padding:8px 2px;font-size:11px;color:var(--dim)">${nodes.length} 实例节点 · ${edges.length} 关系边 · 动态业务域(${domains.join('/')}) · 跨行业自适应 · 左右上下拖动看全图</div>
    <div style="padding:4px 2px">${legend}</div>`;
}
