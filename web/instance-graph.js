/* instance-graph.js — 本体实例数据 SVG 动态大图(力导向布局, 可上下左右滚动)
   数据: /graph/full 返回全部节点+边; 换数据自动重新建模 → 新大图 → 新检索关系 */
const GRAPH_COLORS = {Product:"#2f6bff",Supplier:"#27ae60",Inventory:"#f39c12",Sale:"#e74c3c",Customer:"#8e44ad",Equipment:"#16a085",Category:"#95a5a6"};

async function loadGraphFull(){
  const el=document.getElementById('ontology-graph');
  let r;
  try{ r=await api('/graph/full'); }catch(e){ el.innerHTML='<div class="empty">实例图加载失败</div>';return; }
  if(!r.ok||!r.nodes||!r.nodes.length){ el.innerHTML='<div class="empty">无实例数据</div>';return; }
  const nodes=r.nodes, edges=r.edges||[];
  // 分环种子布局(企业/产品为中心): Category最内, Product内环, 供应链/销售中环, 客户/设备外环
  const W=1100,H=620,cx=W/2,cy=H/2;
  const ring={Category:0,Product:70,Inventory:130,Supplier:130,Sale:190,Equipment:190,Customer:260};
  const pos={}, ringCount={};
  nodes.forEach(n=>{ ringCount[n.entity]=(ringCount[n.entity]||0)+1; });
  nodes.forEach(n=>{
    const r=ring[n.entity]||150;
    const k=ringCount[n.entity]||1, idx=ringCount[n.entity]?--ringCount[n.entity]:0;
    const ang=2*Math.PI*idx/k + (n.entity==='Product'?0.3:0);
    pos[n.id]={x:cx+Math.cos(ang)*r, y:cy+Math.sin(ang)*r};
  });
  // 企业中心节点(核心可见)
  const hubNode={id:'__hub__',entity:'Category',name:'企业'};
  pos['__hub__']={x:cx,y:cy};
  const allNodes=[hubNode].concat(nodes);
  const rep=(a,b)=>{ const dx=a.x-b.x,dy=a.y-b.y; const d=Math.max(Math.sqrt(dx*dx+dy*dy),30); const f=2000/(d*d); return {fx:dx/d*f, fy:dy/d*f}; };
  for(let it=0;it<60;it++){
    allNodes.forEach(n=>{ n.fx=n.fy=0; });
    for(let i=0;i<allNodes.length;i++)for(let j=i+1;j<allNodes.length;j++){
      const f=rep(pos[allNodes[i].id],pos[allNodes[j].id]);
      allNodes[i].fx=(allNodes[i].fx||0)+f.fx; allNodes[i].fy=(allNodes[i].fy||0)+f.fy;
      allNodes[j].fx=(allNodes[j].fx||0)-f.fx; allNodes[j].fy=(allNodes[j].fy||0)-f.fy;
    }
    edges.forEach(e=>{
      const a=pos[e.from],b=pos[e.to]; if(!a||!b)return;
      const dx=b.x-a.x,dy=b.y-a.y; const d=Math.max(Math.sqrt(dx*dx+dy*dy),1);
      const k=0.03*(d-60);
      a.x+=dx/d*k; a.y+=dy/d*k; b.x-=dx/d*k; b.y-=dy/d*k;
    });
    allNodes.forEach(n=>{ pos[n.id].x+=Math.max(-8,Math.min(8,n.fx||0)); pos[n.id].y+=Math.max(-8,Math.min(8,n.fy||0)); });
    allNodes.forEach(n=>{ pos[n.id].x=Math.max(30,Math.min(W-30,pos[n.id].x)); pos[n.id].y=Math.max(30,Math.min(H-30,pos[n.id].y)); });
  }
  // 企业中心节点锚定(核心始终可见)
  pos['__hub__']={x:cx,y:cy};
  // 渲染 SVG(大画布, 容器可滚动)
  let svg=`<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">`;
  edges.forEach(e=>{
    const a=pos[e.from],b=pos[e.to]; if(!a||!b)return;
    svg+=`<line x1="${a.x.toFixed(1)}" y1="${a.y.toFixed(1)}" x2="${b.x.toFixed(1)}" y2="${b.y.toFixed(1)}" stroke="#d6e4ff" stroke-width="1"/>`;
  });
  nodes.forEach(n=>{
    const p=pos[n.id],c=GRAPH_COLORS[n.entity]||"#95a5a6";
    svg+=`<g><circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="${n.entity==='Category'?10:7}" fill="${c}" opacity=".85"/>
    <text x="${p.x.toFixed(1)}" y="${(p.y-10).toFixed(1)}" font-size="${n.entity==='Category'?11:9}" fill="#1a2233" text-anchor="middle">${esc(n.name||n.id_val)}</text></g>`;
  });
  // 企业中心节点(核心)
  svg+=`<g><circle cx="${cx}" cy="${cy}" r="30" fill="#2f6bff" opacity=".95"/>
    <text x="${cx}" y="${cy-2}" font-size="15" font-weight="700" fill="#fff" text-anchor="middle">企业</text>
    <text x="${cx}" y="${cy+12}" font-size="10" fill="#fff" text-anchor="middle">${nodes.length}节点</text></g>`;
  svg+=`</svg>`;
  // 图例
  const legend=Object.entries(GRAPH_COLORS).map(([k,v])=>`<span style="display:inline-block;margin-right:10px;font-size:11px;color:var(--dim)"><i style="display:inline-block;width:9px;height:9px;border-radius:50%;background:${v};margin-right:4px"></i>${k}</span>`).join('');
  el.innerHTML=`<div class="graph-scroll">${svg}</div>
    <div style="padding:8px 2px;font-size:11px;color:var(--dim)">${nodes.length} 节点 · ${edges.length} 边 · 拖动滚动条看全图 · 换数据自动重新建模生成新大图新检索关系</div>
    <div style="padding:4px 2px">${legend}</div>`;
}
