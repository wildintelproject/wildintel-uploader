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
 (("No visit before",None),[("Installation","Deployed","camera and card → active"),("Not visited","Not visited","no entity changes")]),
 (("Deployed","Collected"),[("Revision","Deployed","card collected → ready · card left → active"),
   ("Revision + Desinstallation + Installation  (replacement)","Deployed","old camera, card → ready · new → active"),
   ("Revision + Desinstallation","No camera","camera and card → ready"),
   ("Revision + Desinstallation + Archive","No camera","camera, card → ready · site archived")]),
 (("Deployed","Stolen"),[("Stolen","No camera","camera and its card → archived (stolen)"),
   ("Stolen + Installation  (stolen and replaced)","Deployed","stolen ones archived · new → active"),
   ("Stolen + Archive","No camera","camera, card and site → archived")]),
 (("Deployed","Deployed"),[("Not visited","Not visited","no entity changes")]),
 (("No camera","final"),[("Installation","Deployed","camera and card → active"),("Archive  (alone)","No camera","site → archived"),("Not visited","Not visited","no entity changes")]),
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
HEADS=((30,"THE VISIT BEFORE"),(235,"ACTIONS OF THIS VISIT"),(550,"IT IS LEFT"),(670,"CAMERAS, CARDS AND SITE"))
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
