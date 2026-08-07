/* instance-graph.js — 企业级本体大图(ECharts graph: 域列结构 + roam缩放平移 + hover标签防重叠)
   布局: 企业顶部 → 业务域列(动态) → 实体类 → 实例
   数据: /graph/full 含 domains + node.domain; 换数据/行业自动重建
   技术: ECharts graph(layout:none 手动域列位置 + roam 缩放平移 + 标签hover显示避免重叠 + 分类着色) */
const GRAPH_COLORS = {Product:"#2f6bff",Supplier:"#27ae60",Inventory:"#f39c12",Sale:"#e74c3c",Customer:"#8e44ad",Equipment:"#16a085",Category:"#95a5a6",Purchase:"#e67e22",Production:"#1abc9c",Payment:"#c0392b"};

async function loadGraphFull(){
  const el=document.getElementById('ontology-graph');
  let r;
  try{ r=await api('/graph/full'); }catch(e){ el.innerHTML='<div class="empty">实例图加载失败</div>';return; }
  if(!r.ok||!r.nodes||!r.nodes.length){ el.innerHTML='<div class="empty">无实例数据</div>';return; }
  if(typeof echarts==='undefined'){ el.innerHTML='<div class="empty">ECharts 未加载</div>';return; }
  const nodes=r.nodes, edges=r.edges||[];
  // 域列表从节点实际 domain 构建(含 Category 的 其他域, 避免 domainX 缺键→NaN)
  const domains=[...new Set(nodes.map(n=>n.domain||"其他域"))];
  const grp={}; nodes.forEach(n=>{ (grp[n.entity]=grp[n.entity]||[]).push(n); });
  const entityDomain={}; nodes.forEach(n=>{ entityDomain[n.entity]=n.domain||"其他域"; });

  // 域列位置(企业顶部 → 业务域列 → 实体类 → 实例), 用大坐标空间计算
  const W=1560,H=980, colW=300, topY=70, cx=W/2;
  const pos={};
  pos['__hub__']={x:cx,y:topY};
  const startX=100, gap=280;
  const domainX={}; domains.forEach((d,di)=>{ domainX[d]=startX+di*gap; });
  const entityY={};
  Object.keys(entityDomain).forEach(et=>{
    const dx=domainX[entityDomain[et]];
    if(!entityY[entityDomain[et]]) entityY[entityDomain[et]]=topY+110;
    let y=entityY[entityDomain[et]];
    pos['__cls__'+et]={x:dx+colW/2, y:y};
    y+=34;
    (grp[et]||[]).forEach((n,i)=>{
      const col=(i%6); pos[n.id]={x:dx+40+col*46, y:y+Math.floor(i/6)*46};
    });
    entityY[entityDomain[et]]=y+Math.ceil((grp[et]||[]).length/6)*46+44;
  });
  // 归一化缩放到容器尺寸(否则layout:'none'原始坐标超出画布→空白); 过滤NaN
  const cw=el.clientWidth||720, ch=el.clientHeight||480;
  let minX=Infinity,maxX=-Infinity,minY=Infinity,maxY=-Infinity;
  Object.values(pos).forEach(p=>{ if(p.x==null||p.y==null||isNaN(p.x)||isNaN(p.y))return;
    minX=Math.min(minX,p.x);maxX=Math.max(maxX,p.x);minY=Math.min(minY,p.y);maxY=Math.max(maxY,p.y); });
  const sx=(cw-60)/((maxX-minX)||1), sy=(ch-60)/((maxY-minY)||1), s=Math.min(sx,sy,1);
  Object.keys(pos).forEach(k=>{ if(pos[k].x==null||isNaN(pos[k].x))return; pos[k]={x:30+(pos[k].x-minX)*s, y:30+(pos[k].y-minY)*s}; });
  const cx2=cw/2, topY2=pos['__hub__'].y;

  // ECharts graph
  const categories=Object.keys(grp).map(et=>({name:et}));
  const data=[{id:'__hub__',name:'企业',x:cx2,y:topY2,category:null,symbolSize:64,
               itemStyle:{color:'#2f6bff'},label:{show:true,fontSize:16,fontWeight:'bold',color:'#fff'}}];
  const nodeIds=new Set(['__hub__']);
  nodes.forEach(n=>{
    const p=pos[n.id]; if(!p)return;  // 守卫: 无位置节点跳过
    nodeIds.add(n.id);
    data.push({id:n.id,name:n.name||n.id_val,x:p.x,y:p.y,
      category:categories.findIndex(c=>c.name===n.entity),
      symbolSize:n.entity==='Category'?16:10,
      itemStyle:{color:GRAPH_COLORS[n.entity]||'#7f8c8d'},
      tooltip:{formatter:`<b>${n.entity}</b> ${n.name||n.id_val}<br/>域: ${n.domain||''}`}});
  });
  // links 只保留两端都在 data 的(否则 ECharts 引用不存在节点→渲染异常)
  const links=edges.map(e=>({source:e.from,target:e.to})).filter(l=>nodeIds.has(l.source)&&nodeIds.has(l.target));
  // 企业 hub → 各实体类代表节点(企业拥有/运营所有业务对象, 体现关联度)
  Object.keys(grp).forEach(et=>{
    const rep=(grp[et]||[])[0]; if(rep&&rep.id&&nodeIds.has(rep.id))
      links.push({source:'__hub__',target:rep.id,lineStyle:{color:'#2f6bff',opacity:0.35,width:1.5},label:{show:false}});
  });
  const legend=Object.entries(GRAPH_COLORS).filter(([k])=>grp[k]).map(([k,v])=>`<span style="display:inline-block;margin-right:12px;font-size:11px;color:var(--dim)"><i style="display:inline-block;width:9px;height:9px;border-radius:50%;background:${v};margin-right:4px"></i>${k}</span>`).join('');
  // 先建 chart div + legend(避免 innerHTML+= 清掉 canvas)
  el.innerHTML=`<div id="ontchart" style="height:480px;width:100%"></div>
    <div style="padding:6px 2px;font-size:11px;color:var(--dim)">${nodes.length} 实例 · ${edges.length} 关系 · 拖动缩放看全图 · 悬停看详情 · 动态域(${domains.join('/')})</div>
    <div style="padding:2px">${legend}</div>`;
  if(window._ontChart) window._ontChart.dispose();  // 防重复 init
  const chart=echarts.init(document.getElementById('ontchart'));
  chart.setOption({
    tooltip:{show:true},
    animationDuration:800,
    series:[{
      type:'graph', layout:'force', roam:true,  // 力导向自动分离节点(避免手动坐标错误/重叠)
      force:{repulsion:320, edgeLength:[60,140], gravity:0.1, friction:0.6},
      label:{show:true,position:'right',fontSize:9,color:'#1a2233',formatter:p=>p.name&&p.name.slice(0,10)},
      edgeSymbol:['none','arrow'], edgeSymbolSize:[0,6],
      lineStyle:{color:'#d6e4ff',width:1,curveness:0.1},
      categories, data, links,
      emphasis:{focus:'adjacency',label:{show:true,fontSize:11,fontWeight:'bold'}}
    }]
  });
  window._ontChart=chart;
}
window.addEventListener('resize',()=>{ if(window._ontChart) window._ontChart.resize(); });

// 导出 ECharts 完整图到桌面(高分辨率, ECharts原样式复刻)
async function exportPng(){
  if(!window._ontChart) return alert('请先打开本体建模图');
  const chart=window._ontChart, el=document.getElementById('ontchart');
  const oldW=el.style.width, oldH=el.style.height;
  // 临时放大容器→高清全图(原样式, 非变形)
  el.style.width='1600px'; el.style.height='1000px';
  chart.resize();
  await new Promise(r=>setTimeout(r,150));  // 等渲染
  const dataUrl=chart.getDataURL({type:'png',pixelRatio:2,backgroundColor:'#ffffff'});
  // 还原容器
  el.style.width=oldW; el.style.height=oldH; chart.resize();
  const r=await api('/export/ontology-png',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({data:dataUrl,filename:'企业本体图.png'})});
  alert(r.ok?('已保存到桌面: '+r.path):('导出失败: '+r.error));
}
