/* instance-graph.js — 企业级价值链本体大图(企业中心, 价值流辐射, 双向滚动)
   布局: 企业中心 → 价值流(采购/生产/库存/销售/回款)中环 → 资源(供应商/产品/设备/客户)外环
   数据: /graph/full; 换数据自动重新建模 → 新大图 → 新检索关系 */
const GRAPH_COLORS = {Product:"#2f6bff",Supplier:"#27ae60",Inventory:"#f39c12",Sale:"#e74c3c",Customer:"#8e44ad",Equipment:"#16a085",Category:"#95a5a6",Purchase:"#e67e22",Production:"#1abc9c",Payment:"#c0392b"};

async function loadGraphFull(){
  const el=document.getElementById('ontology-graph');
  let r;
  try{ r=await api('/graph/full'); }catch(e){ el.innerHTML='<div class="empty">实例图加载失败</div>';return; }
  if(!r.ok||!r.nodes||!r.nodes.length){ el.innerHTML='<div class="empty">无实例数据</div>';return; }
  const nodes=r.nodes, edges=r.edges||[];
  // 企业级布局: 大画布 1500x950, 企业中心, 价值流(采购/生产/库存/销售/回款)中环, 资源外环
  const W=1500,H=950,cx=W/2,cy=H/2;
  const ring={
    Category:110,Product:110,           // 产品/类别内环(核心资源)
    Purchase:210,Production:210,Inventory:210,Sale:210,Payment:210,  // 价值流中环
    Supplier:320,Customer:320,Equipment:320  // 资源外环
  };
  const pos={}, grp={};
  nodes.forEach(n=>{ (grp[n.entity]=grp[n.entity]||[]).push(n); });
  Object.keys(grp).forEach(et=>{
    const arr=grp[et], r=ring[et]||200, k=arr.length;
    arr.forEach((n,i)=>{ const ang=2*Math.PI*i/k + (et==='Product'?0.2:0); pos[n.id]={x:cx+Math.cos(ang)*r, y:cy+Math.sin(ang)*r}; });
  });
  pos['__hub__']={x:cx,y:cy};
  // 企业 → 价值流 辐射线(让价值链清晰)
  const flows=['Purchase','Production','Inventory','Sale','Payment'];
  const flowLinks=(grp['Purchase']||[]).concat(grp['Production']||[],grp['Inventory']||[],grp['Sale']||[],grp['Payment']||[]);
  // 渲染 SVG(大画布, 容器强制滚动)
  let svg=`<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">`;
  // 中心辐射线(企业 → 价值流)
  flowLinks.forEach(n=>{ const p=pos[n.id]; if(p) svg+=`<line x1="${cx}" y1="${cy}" x2="${p.x}" y2="${p.y}" stroke="#2f6bff" stroke-width="1.2" opacity=".22"/>`; });
  // 关系边
  edges.forEach(e=>{
    const a=pos[e.from],b=pos[e.to]; if(!a||!b)return;
    svg+=`<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" stroke="#d6e4ff" stroke-width="1"/>`;
  });
  // 企业中心节点
  svg+=`<g><circle cx="${cx}" cy="${cy}" r="38" fill="#2f6bff" stroke="#fff" stroke-width="2"/>
    <text x="${cx}" y="${cy+5}" font-size="19" font-weight="700" fill="#fff" text-anchor="middle">企业</text>
    <text x="${cx}" y="${cy+21}" font-size="10" fill="#fff" text-anchor="middle">${nodes.length}节点</text></g>`;
  // 价值流标签(中环, 加粗显示)
  ['Purchase','Production','Inventory','Sale','Payment'].forEach(fl=>{
    const arr=grp[fl]||[]; if(!arr.length)return;
    const p=pos[arr[0].id];
    svg+=`<text x="${p.x}" y="${p.y}" font-size="13" font-weight="700" fill="${GRAPH_COLORS[fl]}" text-anchor="middle" transform="translate(0,-24)">${fl}(${arr.length})</text>`;
  });
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
    <div style="padding:8px 2px;font-size:11px;color:var(--dim)">${nodes.length} 节点 · ${edges.length} 边 · 价值流(采购→生产→库存→销售→回款) · 左右上下拖动看全图 · 换数据自动重建</div>
    <div style="padding:4px 2px">${legend}</div>`;
}
