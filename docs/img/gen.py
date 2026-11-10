"""Generates the .drawio files of the diagrams of the manual (visit-states, visit-actions, deployment, collection), to be edited in draw.io.

Run it from anywhere: python3 docs/img/gen.py — the files are written next to it. After editing one in draw.io, export it as SVG (File > Export as > SVG)
over the .svg of the same name; the manual shows the SVG. Running this again overwrites the .drawio files.
"""
from pathlib import Path
from xml.sax.saxutils import quoteattr

OUT = str(Path(__file__).resolve().parent) + "/"

class D:
    def __init__(s,name,w,h): s.name=name;s.w=w;s.h=h;s.c=[];s.n=2
    def box(s,x,y,w,h,title,sub,fill,stroke,tc,sc,dash=None,rr=12,fs=14,tag=None,label_only=False):
        i=tag or f"n{s.n}";s.n+=1
        v=f'<b>{title}</b>'+(f'<br><font style="font-size:11px" color="{sc}">{sub}</font>' if sub else '')
        st=(f'rounded=1;arcSize={rr};whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};strokeWidth=2;'
            f'fontColor={tc};fontSize={fs};'+(f'dashed=1;dashPattern={dash};' if dash else ''))
        s.c.append(f'<mxCell id="{i}" value={quoteattr(v)} style="{st}" vertex="1" parent="1"><mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')
        return i
    def text(s,x,y,w,h,t,size=12,color="#64748b",bold=True,align="left"):
        i=f"n{s.n}";s.n+=1
        st=f'text;html=1;fontSize={size};fontColor={color};fontStyle={1 if bold else 0};align={align};verticalAlign=middle;spacingLeft=0;'
        s.c.append(f'<mxCell id="{i}" value={quoteattr(t)} style="{st}" vertex="1" parent="1"><mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')
    def edge(s,a,b,label="",pts=None,exit=None,entry=None):
        pg=('<Array as="points">'+''.join(f'<mxPoint x="{x}" y="{y}"/>' for x,y in pts)+'</Array>') if pts else ''
        i=f"n{s.n}";s.n+=1
        st='edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;endArrow=block;endFill=1;strokeColor=#475569;strokeWidth=2.5;fontSize=11;fontColor=#475569;labelBackgroundColor=#ffffff;'
        if exit: st+=f'exitX={exit[0]};exitY={exit[1]};exitDx=0;exitDy=0;'
        if entry: st+=f'entryX={entry[0]};entryY={entry[1]};entryDx=0;entryDy=0;'
        s.c.append(f'<mxCell id="{i}" value={quoteattr(label)} style="{st}" edge="1" parent="1" source="{a}" target="{b}"><mxGeometry relative="1" as="geometry">{pg}</mxGeometry></mxCell>')
    def save(s,fn):
        x=(f'<mxfile host="app.diagrams.net"><diagram name={quoteattr(s.name)} id="d1"><mxGraphModel dx="1000" dy="600" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="{s.w}" pageHeight="{s.h}" math="0" shadow="0"><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
           +''.join(s.c)+'</root></mxGraphModel></diagram></mxfile>')
        open(OUT+fn,'w').write(x)

GRAY=("#f1f5f9","#64748b","#334155","#475569"); AMB=("#fffbeb","#f59e0b","#92400e","#b45309")
GRN=("#ecfdf5","#10b981","#065f46","#047857"); RED=("#fef2f2","#ef4444","#991b1b","#b91c1c")
NOS=("#ffffff","#94a3b8","#475569","#64748b"); BLU=("#eff6ff","#2563eb","#1e3a8a","#1d4ed8")

# ---- actions: what can be done in a visit, by the state of the visit before it — as a drawio and as the svg the manual shows
STATE={"Deployed":AMB,"Collected":GRN,"Stolen":RED,"Not visited":GRAY,"No camera":NOS}
GROUPS=[
 (("No visit before",None),[("Installation","Deployed","site, camera, card: ready → active"),("Not visited","Not visited","no entity changes")]),
 (("Deployed","Collected"),[("Revision","Deployed","card collected → ready · left → active"),
   ("Revision + Desinstallation + Installation  (replacement)","Deployed","old camera, card → ready · new → active"),
   ("Revision + Desinstallation","No camera","site, camera, card → ready"),
   ("Revision + Desinstallation + Archive","No camera","camera, card → ready · site → archived")]),
 (("Deployed","Stolen"),[("Stolen","No camera","camera, card → archived · site → ready"),
   ("Stolen + Installation  (stolen and replaced)","Deployed","stolen ones archived · new → active"),
   ("Stolen + Archive","No camera","camera, card, site → archived")]),
 (("Deployed","Deployed"),[("Not visited","Not visited","no entity changes")]),
 (("No camera","final"),[("Installation","Deployed","site, camera, card: ready → active"),("Archive  (alone)","No camera","site → archived"),("Not visited","Not visited","no entity changes")]),
]
PITCH,GAP,TOP=34,12,100
def _layout():
    y=TOP;out=[]
    for head,rows in GROUPS:
        out.append((head,rows,y));y+=len(rows)*PITCH+GAP
    return out,y
LAY,ENDY=_layout()
H=ENDY+40
d=D("The actions of a visit",920,H)
d.text(30,22,600,28,"THE ACTIONS OF A VISIT, BY THE STATE OF THE VISIT BEFORE IT",15,"#2563eb")
HEADS=((30,"THE VISIT BEFORE"),(235,"ACTIONS OF THIS VISIT"),(550,"IT IS LEFT"),(670,"SITE, CAMERA AND CARD"))
for x,t in HEADS: d.text(x,62,300,24,t,11)
svg=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 920 {H}" width="920" height="{H}" role="img" aria-labelledby="t d" font-family="Inter, \'Segoe UI\', Roboto, Helvetica, Arial, sans-serif">',
 '  <title id="t">The actions of a visit</title>',
 '  <desc id="d">For each state of the visit before it — Deployed becoming Collected or Stolen, Deployed staying so, No camera, or no visit before — the actions a visit can do, the state it is left in and what it does to the cameras, the cards and the site.</desc>',
 '  <defs><marker id="a" viewBox="0 0 10 10" refX="8" refY="5" markerUnits="userSpaceOnUse" markerWidth="11" markerHeight="11" orient="auto"><path d="M0 0 L10 5 L0 10 z" fill="#475569" /></marker></defs>',
 f'  <rect x="0" y="0" width="920" height="{H}" rx="18" fill="#ffffff" stroke="#d4d4d8" />',
 '  <text x="30" y="40" font-size="15" font-weight="700" fill="#2563eb" letter-spacing="1">THE ACTIONS OF A VISIT, BY THE STATE OF THE VISIT BEFORE IT</text>']
for x,t in HEADS: svg.append(f'  <text x="{x}" y="78" font-size="11" font-weight="700" fill="#64748b" letter-spacing="1">{t}</text>')
def chip_svg(x,y,w,name,dash=False,label=None):
    f,st,tc,_=STATE.get(name,GRAY)
    return (f'  <rect x="{x}" y="{y}" width="{w}" height="24" rx="8" fill="{f}" stroke="{st}" stroke-width="2"'+(' stroke-dasharray="4 3"' if dash else '')+' />'
            f'<text x="{x+w/2}" y="{y+16}" font-size="11.5" font-weight="700" fill="{tc}" text-anchor="middle">{label or name}</text>')
for (head,rows,y0) in LAY:
    h=len(rows)*PITCH-4; cy=y0+h/2
    svg.append(f'  <rect x="30" y="{y0}" width="190" height="{h}" rx="10" fill="#f8fafc" stroke="#e2e8f0" />')
    gid=d.box(30,y0,190,h,"","","#f8fafc","#e2e8f0","#334155","#475569",rr=10)
    if head[1] is None:
        svg.append(chip_svg(38,cy-12,174,"No visit before",True)); d.box(38,cy-12,174,24,"No visit before","",*GRAY[:1],"#94a3b8","#475569","#475569","4 3",rr=30,fs=11)
    elif head[1]=="final":
        svg.append(chip_svg(38,cy-12,174,"No camera",label="No camera · final state")); d.box(38,cy-12,174,24,"No camera · final state","",*STATE["No camera"][:3],STATE["No camera"][3],rr=30,fs=11)
    else:
        svg.append(chip_svg(38,cy-12,76,head[0])+chip_svg(136,cy-12,76,head[1])+f'<path d="M116 {cy} H134" stroke="#475569" stroke-width="2.5" fill="none" marker-end="url(#a)" />')
        c1=d.box(38,cy-12,76,24,head[0],"",*STATE[head[0]][:3],STATE[head[0]][3],rr=30,fs=11); c2=d.box(136,cy-12,76,24,head[1],"",*STATE[head[1]][:3],STATE[head[1]][3],rr=30,fs=11)
        d.edge(c1,c2)
    for i,(act,res,ent) in enumerate(rows):
        y=y0+i*PITCH; m=y+(PITCH-4)/2
        svg.append(f'  <path d="M220 {cy} H228 V{m} H235" stroke="#cbd5e1" stroke-width="1.5" fill="none" />')
        svg.append(f'  <rect x="235" y="{m-13}" width="300" height="26" rx="13" fill="#ffffff" stroke="#cbd5e1" /><text x="385" y="{m+4}" font-size="11.5" fill="#334155" text-anchor="middle">{act}</text>')
        svg.append(f'  <path d="M535 {m} H548" stroke="#475569" stroke-width="2.5" fill="none" marker-end="url(#a)" />')
        svg.append(chip_svg(550,m-12,105,res))
        svg.append(f'  <text x="670" y="{m+4}" font-size="10.5" fill="#475569">{ent}</text>')
        p=d.box(235,m-13,300,26,act.replace("  "," "),"","#ffffff","#cbd5e1","#334155","#475569",rr=50,fs=11)
        r=d.box(550,m-12,105,24,res,"",*STATE[res][:3],STATE[res][3],rr=30,fs=11)
        d.edge(p,r)
        d.text(670,m-10,230,20,ent,10.5,"#475569",False)
note="A visit before that was not visited does not count: the one before it decides. After an Archive the site is closed: no visit follows."
svg.append(f'  <text x="30" y="{ENDY+22}" font-size="12" fill="#64748b">{note}</text>')
d.text(30,ENDY+10,860,24,note,12,"#64748b",False)
svg.append('</svg>\n')
open(OUT+"visit-actions.svg","w",encoding="utf-8").write("\n".join(svg))
d.save("visit-actions.drawio")

# ---- states
d=D("The states of a visit",920,420)
d.text(40,28,400,28,"THE STATES OF A VISIT",15,"#2563eb")
for x,t in ((40,"BEFORE IT IS REGISTERED"),(520,"WHAT THE VISIT DID"),(720,"WHEN A LATER VISIT…")):
    d.text(x,70,200,28,t)
pl=d.box(30,104,170,76,"Planned","not made yet",GRAY[0],"#94a3b8","#334155","#475569","6 5",fs=17)
un=d.box(30,300,170,76,"Unknown","nothing is known of it","#f5f3ff","#a78bfa","#5b21b6","#6d28d9","6 5",fs=17)
rg=d.box(262,210,116,68,"The visit is<br>registered","",*BLU[:1],"#2563eb","#1e3a8a","#1e3a8a",rr=50)
dp=d.box(470,104,170,76,"Deployed","a camera is out",*AMB,fs=17)
ns=d.box(470,214,170,68,"No camera","no camera is out",*NOS)
nv=d.box(470,316,170,76,"Not visited","it could not be made",*GRAY,fs=17)
co=d.box(720,104,170,76,"Collected","its card was collected",*GRN,fs=17)
st=d.box(720,222,170,76,"Stolen","no images to import",*RED,fs=17)
d.edge(pl,rg,"it is made",exit=(0.5,1),entry=(0,0.35),pts=[(115,222),(262,222)])
d.edge(un,rg,"it is filled in",exit=(0.5,0),entry=(0,0.65),pts=[(115,266),(262,266)])
d.edge(rg,dp,"left a camera",exit=(1,0.2),entry=(0,0.5),pts=[(455,224),(455,142)])
d.edge(rg,ns,"left no camera",exit=(1,0.5),entry=(0,0.5))
d.edge(rg,nv,"not revised",exit=(1,0.8),entry=(0,0.5),pts=[(455,265),(455,354)])
d.edge(dp,co,"collects its card",exit=(1,0.25),entry=(0,0.25))
d.edge(dp,st,"finds the camera stolen",exit=(1,0.75),entry=(0,0.5),pts=[(682,161),(682,260)])
d.save("visit-states.drawio")

BLUB=("#eff6ff","#2563eb","#1e3a8a","#1e40af")
# ---- deployment
d=D("A deployment",920,400)
d.text(40,28,800,28,"A DEPLOYMENT IS THE IMAGES BETWEEN TWO CONSECUTIVE VISITS",15,"#2563eb")
d.box(40,58,840,34,"One location — some GPS coordinates and a timezone — one camera","",GRAY[0],"#94a3b8","#334155","#475569",rr=50,fs=13)
d.text(40,108,300,28,"THE VISIT THAT LEFT THE CAMERA"); d.text(580,108,300,28,"THE NEXT VISIT",align="right")
v1=d.box(40,136,170,104,"Visit R0001","left the camera<br>and its card",*AMB,fs=17)
dep=d.box(240,128,460,120,"Deployment R0001-DONA_01","the images taken by the camera between the two visits,<br>set up with the same height, tilt, delay between triggers…",*BLUB,fs=14)
v2=d.box(710,136,170,104,"Visit R0002","collected<br>the card",*GRN,fs=17)
d.edge(v1,dep);d.edge(dep,v2)
d.text(40,268,200,28,"ITS STATE")
d.box(40,296,270,76,"Open","the camera is still out: the<br>card has not been collected",*AMB,dash="6 5",fs=15)
d.box(325,296,270,76,"Closed","the card is collected: its<br>images can be imported",*GRN,fs=15)
d.box(610,296,270,76,"Camera stolen","the deployment is closed<br>and has no images",*RED,fs=15)
d.save("deployment.drawio")

# ---- collection
d=D("A collection",920,436)
d.text(40,28,800,28,"A COLLECTION IS ALL THE DEPLOYMENTS OF A REVISION",15,"#2563eb")
d.box(266,62,218,278,"Collection R0001","all closed","#eff6ff","#bfdbfe","#1e3a8a","#475569",rr=5,fs=16)
d.box(516,62,218,278,"Collection R0002","2 closed, 2 open","#eff6ff","#bfdbfe","#1e3a8a","#475569",rr=5,fs=16)
d.c[-2:]=[c.replace('fontColor=','verticalAlign=top;spacingTop=8;fontColor=') for c in d.c[-2:]]
for i,s in enumerate(["WICP_02_001","WICP_02_002","WICP_02_003","WICP_02_004"]):
    y=166+i*48
    d.text(40,y-14,180,28,s,13,"#334155")
    d.box(278,y-14,204,28,f"R0001-{s}","",*GRN[:3],GRN[3],fs=11)
    op=i>=2
    d.box(528,y-14,204,28,f"R0002-{s}","",*(AMB if op else GRN),dash="5 4" if op else None,fs=11)
    for cx,pl in ((250,False),(500,False),(750,op)):
        d.box(cx-15,y-15,30,30,"" if pl else "✓","",
              *(("#f8fafc","#94a3b8","#94a3b8","#94a3b8") if pl else ("#dcfce7","#16a34a","#15803d","#15803d")),dash="4 4" if pl else None,rr=50,fs=14)
for x,t in ((250,"visits R0001"),(500,"visits R0002"),(750,"visits R0003")): d.text(x-60,348,120,24,t,12,"#64748b",align="center")
d.text(40,380,800,24,"closed deployment: the next visit has collected its card · open deployment (dashed): the card is still to be collected",12,"#475569",False)
d.text(40,412,840,24,"A deployment belongs to the revision of the visit that left the camera: R0001-WICP_02_001 is of R0001.",12,"#64748b",False)
d.save("collection.drawio")


# ---- the life of the entities: a location, a camera, an SD card — what it is, and the states it goes through
def _esc(t): return t.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
LC={"Planned":("#fffbeb","#f59e0b","#92400e","#b45309"),"Ready":("#eff6ff","#2563eb","#1e3a8a","#1d4ed8"),
    "Active":("#ecfdf5","#10b981","#065f46","#047857"),"Archived":("#f1f5f9","#64748b","#334155","#475569")}
XS=[30,270,510,750]; BW=140
def lifecycle(fn,title,top,subs,labels,back,note,site=False):
    """top: (left, relation, right) boxes of what it is; subs: what each state means (2 lines each); labels: the label on each of the three arrows; back: the label of the way back."""
    import textwrap
    lines=textwrap.wrap(note,115)
    H=380+18*len(lines); svg=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 920 {H}" width="920" height="{H}" role="img" aria-labelledby="t d" font-family="Inter, \'Segoe UI\', Roboto, Helvetica, Arial, sans-serif">',
      f'  <title id="t">{_esc(title)}</title>', f'  <desc id="d">{_esc(note)}</desc>',
      '  <defs><marker id="a" viewBox="0 0 10 10" refX="8" refY="5" markerUnits="userSpaceOnUse" markerWidth="11" markerHeight="11" orient="auto"><path d="M0 0 L10 5 L0 10 z" fill="#475569" /></marker></defs>',
      f'  <rect x="0" y="0" width="920" height="{H}" rx="18" fill="#ffffff" stroke="#d4d4d8" />',
      f'  <text x="30" y="40" font-size="15" font-weight="700" fill="#2563eb" letter-spacing="1">{_esc(title.upper())}</text>']
    d=D(title,920,H); d.text(30,22,800,28,title.upper(),15,"#2563eb")
    # what it is
    (l1,l2),rel,(r1,r2)=top
    svg.append(f'  <rect x="30" y="64" width="260" height="76" rx="12" fill="#f8fafc" stroke="#94a3b8" stroke-width="2" /><text x="160" y="95" font-size="15" font-weight="700" fill="#334155" text-anchor="middle">{_esc(l1)}</text><text x="160" y="117" font-size="11.5" fill="#475569" text-anchor="middle">{_esc(l2)}</text>')
    svg.append(f'  <rect x="630" y="64" width="260" height="76" rx="12" fill="#f8fafc" stroke="#94a3b8" stroke-width="2" /><text x="760" y="95" font-size="15" font-weight="700" fill="#334155" text-anchor="middle">{_esc(r1)}</text><text x="760" y="117" font-size="11.5" fill="#475569" text-anchor="middle">{_esc(r2)}</text>')
    svg.append(f'  <path d="M292 102 H628" stroke="#475569" stroke-width="2.5" fill="none" marker-end="url(#a)" />')
    for i,line in enumerate(rel):
        svg.append(f'  <text x="460" y="{77+i*15}" font-size="11.5" fill="#475569" text-anchor="middle"><tspan>{_esc(line)}</tspan></text>')
    a=d.box(30,64,260,76,l1,l2,"#f8fafc","#94a3b8","#334155","#475569",fs=15); b=d.box(630,64,260,76,r1,r2,"#f8fafc","#94a3b8","#334155","#475569",fs=15); d.edge(a,b,"<br>".join(rel))
    svg.append(f'  <text x="30" y="160" font-size="12" font-weight="700" fill="#64748b" letter-spacing="1">ITS STATES</text>')
    d.text(30,146,300,24,"ITS STATES",12)
    ids=[]
    for x,(name,sub) in zip(XS,subs):
        f,st,tc,sc=LC[name]
        svg.append(f'  <rect x="{x}" y="196" width="{BW}" height="90" rx="12" fill="{f}" stroke="{st}" stroke-width="2" /><text x="{x+BW/2}" y="226" font-size="17" font-weight="700" fill="{tc}" text-anchor="middle">{name}</text>')
        for i,line in enumerate(sub): svg.append(f'  <text x="{x+BW/2}" y="{248+i*15}" font-size="11" fill="{sc}" text-anchor="middle">{_esc(line)}</text>')
        ids.append(d.box(x,196,BW,90,name,"<br>".join(sub),f,st,tc,sc,fs=17))
    for i,lab in enumerate(labels):
        x1=XS[i]+BW; x2=XS[i+1]; w=len(lab)*5.6+22
        svg.append(f'  <path d="M{x1} 241 H{x2}" stroke="#475569" stroke-width="2.5" fill="none" marker-end="url(#a)" />')
        svg.append(f'  <rect x="{(x1+x2)/2-w/2}" y="204" width="{w}" height="20" rx="10" fill="#ffffff" stroke="#cbd5e1" /><text x="{(x1+x2)/2}" y="218" font-size="11" fill="#475569" text-anchor="middle">{_esc(lab)}</text>')
        d.edge(ids[i],ids[i+1],lab)
    # Settings can archive from any state: the way from Planned over the others
    xa=XS[0]+BW/2; xb=XS[3]+BW/2; lab="by settings *" if site else "by settings"; w=len(lab)*5.6+22
    svg.append(f'  <path d="M{xa} 196 V190 Q{xa} 178 {xa+12} 178 H{xb-12} Q{xb} 178 {xb} 190 V194" stroke="#475569" stroke-width="2.5" fill="none" marker-end="url(#a)" />')
    svg.append(f'  <rect x="{(xa+xb)/2-w/2}" y="168" width="{w}" height="20" rx="10" fill="#ffffff" stroke="#cbd5e1" /><text x="{(xa+xb)/2}" y="182" font-size="11" fill="#475569" text-anchor="middle">{lab}</text>')
    d.edge(ids[0],ids[3],lab,exit=(0.5,0),entry=(0.5,0),pts=[(xa,178),(xb,178)])
    if site:   # a ready site is archived by settings too, and goes back to planned by settings
        xr=XS[1]+BW/2
        svg.append(f'  <path d="M{xr} 196 V178" stroke="#475569" stroke-width="2.5" fill="none" />')
        svg.append(f'  <path d="M{XS[1]} 268 H{XS[0]+BW}" stroke="#475569" stroke-width="2.5" fill="none" marker-end="url(#a)" />')
        svg.append(f'  <rect x="{(XS[0]+BW+XS[1])/2-40}" y="258" width="80" height="20" rx="10" fill="#ffffff" stroke="#cbd5e1" /><text x="{(XS[0]+BW+XS[1])/2}" y="272" font-size="11" fill="#475569" text-anchor="middle">by settings *</text>')
        d.edge(ids[1],ids[0],"by settings *",exit=(0,0.8),entry=(1,0.8))
    # the way back, from Active to Ready
    x1=XS[2]+BW/2; x2=XS[1]+BW/2; w=len(back)*5.6+22
    svg.append(f'  <path d="M{x1} 286 V318 Q{x1} 330 {x1-12} 330 H{x2+12} Q{x2} 330 {x2} 318 V288" stroke="#475569" stroke-width="2.5" fill="none" marker-end="url(#a)" />')
    svg.append(f'  <rect x="{(x1+x2)/2-w/2}" y="320" width="{w}" height="20" rx="10" fill="#ffffff" stroke="#cbd5e1" /><text x="{(x1+x2)/2}" y="334" font-size="11" fill="#475569" text-anchor="middle">{_esc(back)}</text>')
    d.edge(ids[2],ids[1],back,exit=(0.5,1),entry=(0.5,1),pts=[(x1,330),(x2,330)])
    for i,line in enumerate(lines):
        svg.append(f'  <text x="30" y="{372+i*18}" font-size="12" fill="#64748b">{_esc(line)}</text>'); d.text(30,360+i*18,860,24,line,12,"#64748b",False)
    svg.append('</svg>\n')
    open(OUT+fn+".svg","w",encoding="utf-8").write("\n".join(svg)); d.save(fn+".drawio")

lifecycle("location","The life of a location",
  (("A GPS coordinate","latitude, longitude, uncertainty"),("+ its information","name · timezone · summer time or not · status"),("A location","a place where a camera can be put up")) if False else (("A GPS coordinate","latitude, longitude and its uncertainty"),["with more information"],("Information","name · timezone · summer time · status")),
  [("Planned",["only in Settings:","not in the app"]),("Ready",["ready to have","a camera"]),("Active",["it has","a camera"]),("Archived",["out of use","for good"])],
  ["by settings","Installation","Archive"],"camera taken away or stolen",
  "* Only when no camera is out and no visit is still to be made in a revision that has begun. Only a visit makes a site active. Archived is final: it never goes back.",site=True)
lifecycle("camera","The life of a camera",
  (("A site","where the camera is put up"),["has one camera","at a time"],("A camera","its id, its model, its settings")),
  [("Planned",["only in Settings:","not in the app"]),("Ready",["available,","not in the field"]),("Active",["put up","at a site"]),("Archived",["lost, stolen","or broken"])],
  ["by settings","Installation","Stolen"],"Desinstallation",
  "A site has one camera at a time, and a camera is at one site at a time. A camera goes to Archived for good: stolen, or lost or broken (from Settings).")
lifecycle("sd-card","The life of an SD card",
  (("A camera","at a site"),["holds one card,","until it is collected"],("An SD card","its label, its brand, its capacity")),
  [("Planned",["only in Settings:","not in the app"]),("Ready",["free: in no","camera"]),("Active",["in a camera","in the field"]),("Archived",["lost, stolen","or broken"])],
  ["by settings","left in a camera","stolen"],"collected",
  "A card is left by an Installation or a Revision and collected by the next Revision or Desinstallation. Stolen with its camera, or lost or broken, it is archived for good.")
