const FPS=30;
const C=window.CONTENT||{};
const ID=window.COMPOSITION_ID;
const COMP=(C.compositions||{})[ID]||{};
const TL=(window.TIMELINE||{})[ID]||{};
const T=value=>value;
const clamp=(value,min,max)=>Math.max(min,Math.min(max,value));
const smooth=value=>{const x=clamp(value,0,1);return x*x*(3-2*x);};

document.head.insertAdjacentHTML('beforeend',`<style>
@font-face{font-family:Saira;src:url(fonts/saira-400.woff2)}
@font-face{font-family:Saira;src:url(fonts/saira-600.woff2);font-weight:600}
*{margin:0;padding:0;box-sizing:border-box}
:root{--background:black;--text:white;--muted:white;--accent:white}
html,body{width:1080px;height:1920px;overflow:hidden;background:var(--background);font-family:Saira,Arial,sans-serif}
#stage{position:relative;width:1080px;height:1920px;overflow:hidden;background:var(--background)}
.scene{position:absolute;inset:0;display:none;background:var(--background)}
.scene canvas{position:absolute;inset:0;width:1080px;height:1920px}
.shade{position:absolute;left:0;right:0;bottom:0;height:670px;background:linear-gradient(180deg,transparent 0%,rgba(0,0,0,.22) 28%,rgba(0,0,0,.82) 100%)}
.copy{position:absolute;left:72px;right:72px;bottom:176px;color:var(--text);text-shadow:0 2px 18px rgba(0,0,0,.38);transform-origin:left bottom}
.copy:empty{display:none}
.kicker{display:flex;align-items:center;gap:18px;margin-bottom:17px;color:var(--accent);font-size:24px;font-weight:600;letter-spacing:3.3px;line-height:1.1}
.kicker:before{content:'';display:block;width:42px;height:3px;background:var(--accent)}
.headline{max-width:900px;font-size:61px;font-weight:600;line-height:1.05;letter-spacing:-1.5px}
.detail{margin-top:20px;color:var(--muted);font-size:27px;line-height:1.2;letter-spacing:.2px}
</style>`);

function applyTheme(theme){
  for(const [key,value] of Object.entries(theme||{}))document.documentElement.style.setProperty('--'+key,T(value));
}
window.applyTheme=applyTheme;
applyTheme(C.theme);

const scenes=(TL.scenes||[]);
document.body.innerHTML='<div id="stage"></div>';
const stage=document.querySelector('#stage');
for(let index=0;index<scenes.length;index++){
  const copy=(COMP.scenes||[])[index]||{};
  const section=document.createElement('section');
  section.className='scene';section.id=scenes[index].id;
  section.innerHTML='<canvas width="1080" height="1920"></canvas><div class="shade"></div><div class="copy"></div>';
  const copyRoot=section.querySelector('.copy');
  for(const key of ['kicker','headline','detail'])if(Object.hasOwn(copy,key)){
    const node=document.createElement('div');node.className=key;node.textContent=T(copy[key]);copyRoot.appendChild(node);
  }
  if(!copyRoot.children.length){copyRoot.remove();section.querySelector('.shade').remove();}
  stage.appendChild(section);
}

const AUTHORED=scenes.map(scene=>[scene.id,+scene.start,+scene.end]);
const SC_EDIT=scenes.map(scene=>['#'+scene.id,+scene.start,+scene.end]);
const WARP_PTS=SC_EDIT.map((scene,index)=>[scene[1],AUTHORED[index][1]])
  .concat([[SC_EDIT[SC_EDIT.length-1][2],AUTHORED[AUTHORED.length-1][2]]]);
function warp(time){
  if(time<=WARP_PTS[0][0])return WARP_PTS[0][1]+time-WARP_PTS[0][0];
  for(let index=1;index<WARP_PTS.length;index++)if(time<=WARP_PTS[index][0]){
    const [x0,y0]=WARP_PTS[index-1], [x1,y1]=WARP_PTS[index];
    return x1>x0?y0+(time-x0)*(y1-y0)/(x1-x0):y1;
  }
  const last=WARP_PTS[WARP_PTS.length-1];
  return last[1]+time-last[0];
}

const clips=(TL.clips||[]).map((clip,index)=>({...clip,scene:'#'+AUTHORED[index][0],authoredStart:AUTHORED[index][1],authoredEnd:AUTHORED[index][2],frames:new Map()}));
const gradeData=TL.grade||{};
const grade=`contrast(${gradeData.contrast??1}) saturate(${gradeData.saturation??1}) brightness(${gradeData.brightness??1})`;
const loadJobs=[];
for(const clip of clips)for(let frame=1;frame<=clip.count;frame++){
  const image=new Image();clip.frames.set(frame,image);
  loadJobs.push(new Promise(resolve=>{image.onload=resolve;image.onerror=resolve;}));
  image.src=`${clip.dir}/f${String(frame).padStart(4,'0')}.jpg`;
}
function frameImage(clip,frame){
  if(clip.frames.has(frame))return clip.frames.get(frame);
  const image=new Image();image.src=`${clip.dir}/f${String(frame).padStart(4,'0')}.jpg`;clip.frames.set(frame,image);return image;
}
function activeClip(time){return clips.find(clip=>time<clip.authoredEnd-1e-7)||clips[clips.length-1];}
function draw(time){
  const clip=activeClip(time);
  for(const item of clips)document.querySelector(item.scene).style.display=item===clip?'block':'none';
  const duration=clip.authoredEnd-clip.authoredStart;
  const local=clamp(time-clip.authoredStart,0,duration-1/FPS);
  const frame=clamp(1+Math.floor(local*clip.fps),1,clip.count);
  const image=frameImage(clip,frame);if(!image||!image.naturalWidth)return;
  const canvas=document.querySelector(clip.scene+' canvas'), context=canvas.getContext('2d');
  const scale=Math.max(1080/clip.width,1920/clip.height), width=clip.width*scale, height=clip.height*scale;
  const x=clamp(540-width*clip.focusX,1080-width,0), y=clamp(960-height*clip.focusY,1920-height,0);
  context.filter=grade;context.drawImage(image,x,y,width,height);
  const copy=document.querySelector(clip.scene+' .copy');
  if(copy){
    const enter=smooth(local/.32), leave=smooth((duration-local)/.28), reveal=Math.min(enter,leave);
    copy.style.opacity=reveal;copy.style.transform=`translateY(${(1-enter)*18}px)`;
  }
}

const DUR=SC_EDIT[SC_EDIT.length-1][2];
window.DUR=DUR;window.FPS=FPS;window.TOTAL_FRAMES=Math.round(DUR*FPS);
window.seek=frame=>{draw(warp(frame/FPS));return true;};
window.readyP=Promise.all(loadJobs).then(()=>{window.seek(0);return true;});
if(location.hash==='#play'){
  const started=performance.now();
  (function play(){const elapsed=(performance.now()-started)/1000;if(elapsed<DUR){window.seek(Math.floor(elapsed*FPS));requestAnimationFrame(play);}})();
}
