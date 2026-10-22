# -------------------------------------------------------
# PREMISSAS ATIVAS:
# 1. Objetivo: gerar arvore de decisao interativa (HTML unico, offline) a partir de YAML; clique na resposta abre so o ramo seguinte
# 2. Constraint: mesmo padrao de uso do unifilar_df.py (YAML de entrada, --saida, ErroEntrada, etapas); exporta Mermaid para Miro
# 3. Stack: Python 3.13 + PyYAML; HTML/CSS/JS sem dependencia externa
# 4. Teste: NAO TESTADO pelo usuario (v0.2 testada so no sandbox com a arvore SIGA)
# -------------------------------------------------------
"""GERADOR DE ARVORE DE DECISAO - Prolux Engenharia.

Uso:
    python arvore_df.py entrada.yaml [--saida PASTA] [--sem-mermaid]

Gera <entrada>.html (navegador, offline) e <entrada>.mmd (Mermaid, para Miro).

Notacao do YAML (v0.2):
    tipo: arvore_decisao
    projeto: {titulo, subtitulo, fonte, revisao}
    inicio: ID
    nos:
    - id: ID                      obrigatorio, unico
      pergunta: texto             no de pergunta (tem 'opcoes')
      opcoes: [{texto, vai}]
      resultado: texto            no de resultado (sem 'opcoes')
      status: ok|atencao|proibido|verificar|info
      segue: ID                   proximo no apos um resultado (opcional)
      ref: "5.2.3"                citacao
      nota: texto                 observacao curta no cartao
      alerta: texto               faixa de alerta no painel lateral
      numeros: [{valor, rotulo}]  destaques grandes no painel lateral
      info: [{titulo, itens:[..]} | {titulo, tabela:[[cab..],[lin..]]}]
      laterais: [ID, ...]         perguntas laterais; abrem no painel, nao mudam o caminho
    lacunas: [texto, ...]
"""
import html
import json
import os
import sys

import yaml

VERSAO = "0.2.0"
STATUS = {"ok", "atencao", "proibido", "verificar", "info"}


class ErroEntrada(Exception):
    pass


# ---------------------------------------------------------------- modelo
class Modelo:
    def __init__(self, cfg):
        if not isinstance(cfg, dict) or cfg.get("tipo") != "arvore_decisao":
            raise ErroEntrada("o YAML precisa ter 'tipo: arvore_decisao'")
        self.cfg = cfg
        self.projeto = cfg.get("projeto") or {}
        self.nos = {}
        for i, n in enumerate(cfg.get("nos") or []):
            if not isinstance(n, dict):
                raise ErroEntrada(f"nó {i + 1} não é um mapa (faltou '- id:'?)")
            nid = str(n.get("id") or "").strip()
            if not nid:
                raise ErroEntrada(f"nó {i + 1} sem id")
            if nid in self.nos:
                raise ErroEntrada(f"id repetido: {nid}")
            self.nos[nid] = n
        if not self.nos:
            raise ErroEntrada("nenhum nó em 'nos'")
        self.inicio = str(cfg.get("inicio") or next(iter(self.nos)))
        if self.inicio not in self.nos:
            raise ErroEntrada(f"inicio '{self.inicio}' não existe")
        self.avisos = []
        self._validar()

    def tipo(self, n):
        return "pergunta" if n.get("opcoes") else "resultado"

    def destinos(self, nid):
        n = self.nos[nid]
        if n.get("opcoes"):
            return [str(o.get("vai") or "") for o in n["opcoes"]]
        return [str(n["segue"])] if n.get("segue") else []

    def _validar(self):
        for nid, n in self.nos.items():
            if n.get("opcoes"):
                if not n.get("pergunta"):
                    raise ErroEntrada(f"{nid}: tem 'opcoes' mas falta 'pergunta'")
                for j, o in enumerate(n["opcoes"]):
                    if not isinstance(o, dict) or not o.get("texto"):
                        raise ErroEntrada(f"{nid} opção {j + 1}: falta 'texto'")
                    if not o.get("vai"):
                        raise ErroEntrada(f"{nid} opção '{o['texto']}': falta 'vai'")
                    if str(o["vai"]) not in self.nos:
                        raise ErroEntrada(f"{nid} opção '{o['texto']}': nó '{o['vai']}' não existe")
            else:
                if not n.get("resultado"):
                    raise ErroEntrada(f"{nid}: nó sem 'opcoes' precisa de 'resultado'")
                if n.get("segue") and str(n["segue"]) not in self.nos:
                    raise ErroEntrada(f"{nid}: segue para '{n['segue']}', que não existe")
            st = str(n.get("status") or "info").lower()
            if st not in STATUS:
                raise ErroEntrada(f"{nid}: status '{st}' inválido; use {', '.join(sorted(STATUS))}")
            for lid in n.get("laterais") or []:
                if str(lid) not in self.nos:
                    raise ErroEntrada(f"{nid}: lateral '{lid}' não existe")
            for k, b in enumerate(n.get("info") or []):
                if isinstance(b, str):
                    continue
                if not isinstance(b, dict) or not (b.get("itens") or b.get("tabela")):
                    raise ErroEntrada(f"{nid} info {k + 1}: precisa de 'itens' ou 'tabela'")
        # ciclo (caminho principal + laterais) e alcance
        cor = {}

        def arestas(nid):
            return self.destinos(nid) + [str(x) for x in self.nos[nid].get("laterais") or []]

        def visita(nid, pilha):
            cor[nid] = 1
            for d in arestas(nid):
                if cor.get(d) == 1:
                    raise ErroEntrada(f"ciclo: {' -> '.join(pilha + [nid, d])}")
                if d not in cor:
                    visita(d, pilha + [nid])
            cor[nid] = 2

        visita(self.inicio, [])
        soltos = [k for k in self.nos if k not in cor]
        if soltos:
            self.avisos.append(f"nós inalcançáveis a partir de '{self.inicio}': {', '.join(soltos)}")

    def json(self):
        nos = {}
        for nid, n in self.nos.items():
            d = {"id": nid, "tipo": self.tipo(n), "status": str(n.get("status") or "info").lower(),
                 "texto": str(n.get("pergunta") or n.get("resultado") or ""),
                 "ref": str(n.get("ref") or ""), "nota": str(n.get("nota") or ""),
                 "alerta": str(n.get("alerta") or ""),
                 "numeros": [{"valor": str(x.get("valor", "")), "rotulo": str(x.get("rotulo", ""))}
                             for x in n.get("numeros") or []],
                 "info": [], "laterais": [str(x) for x in n.get("laterais") or []]}
            for b in n.get("info") or []:
                if isinstance(b, str):
                    d["info"].append({"titulo": "", "itens": [b]})
                elif b.get("tabela"):
                    d["info"].append({"titulo": str(b.get("titulo") or ""),
                                      "tabela": [[str(c) for c in lin] for lin in b["tabela"]]})
                else:
                    d["info"].append({"titulo": str(b.get("titulo") or ""),
                                      "itens": [str(x) for x in b["itens"]]})
            if n.get("opcoes"):
                d["opcoes"] = [{"texto": str(o["texto"]), "vai": str(o["vai"])} for o in n["opcoes"]]
            elif n.get("segue"):
                d["segue"] = str(n["segue"])
            nos[nid] = d
        return {"projeto": {k: str(v) for k, v in self.projeto.items()},
                "inicio": self.inicio, "nos": nos, "lacunas": [str(x) for x in self.cfg.get("lacunas") or []]}


# ---------------------------------------------------------------- mermaid
def mermaid(m):
    def esc(s):
        return str(s).replace('"', "'").replace("\n", "<br/>")

    lin = ["flowchart TD",
           "classDef pergunta fill:#9CE6FF,stroke:#2C97BB,color:#1C4657",
           "classDef ok fill:#B3E65F,stroke:#6E9A24,color:#2F440B",
           "classDef atencao fill:#FFE86D,stroke:#A28E26,color:#574900",
           "classDef proibido fill:#FFB575,stroke:#CC7830,color:#542700",
           "classDef verificar fill:#B8ACFB,stroke:#8A7BE0,color:#231266",
           "classDef info fill:#DDDDD8,stroke:#8A8A7E,color:#434339"]
    for nid, n in m.nos.items():
        txt = esc(n.get("pergunta") or n.get("resultado"))
        if n.get("ref"):
            txt += f"<br/>{esc(n['ref'])}"
        if n.get("opcoes"):
            lin.append(f'{nid}{{"{txt}"}}:::pergunta')
        else:
            lin.append(f'{nid}["{txt}"]:::{str(n.get("status") or "info").lower()}')
    for nid, n in m.nos.items():
        if n.get("opcoes"):
            for o in n["opcoes"]:
                lin.append(f'{nid} -->|{esc(o["texto"])}| {o["vai"]}')
        elif n.get("segue"):
            lin.append(f"{nid} --> {n['segue']}")
        for lid in n.get("laterais") or []:
            lin.append(f"{nid} -.->|lateral| {lid}")
    return "\n".join(lin) + "\n"


# ---------------------------------------------------------------- html
PAGINA = r"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>__TITULO__</title>
<style>
:root{--bg:#f4f5f2;--card:#fff;--fg:#1e2427;--mut:#5d686d;--line:#d3d8d5;--acc:#e0a800;--acc2:#7a5b00;--sel:#fff8dc;
--ok:#2f7d4f;--okb:#e6f4ea;--at:#9a6a00;--atb:#fff4cc;--no:#b23a22;--nob:#fde8e3;--ver:#5b45c4;--verb:#ece8ff;--inf:#4d5a60;--infb:#eef0ef;
--f:"Segoe UI",Roboto,Arial,sans-serif;--m:Consolas,"Cascadia Mono",ui-monospace,monospace}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#15191b;--card:#1d2326;--fg:#e5e9e9;--mut:#9ba6aa;--line:#323b3f;--acc:#f0c030;--acc2:#f0c030;--sel:#2b2a1c;
--ok:#7fcf9c;--okb:#173323;--at:#f0c030;--atb:#3a3112;--no:#f29a85;--nob:#3d1d16;--ver:#b6a8ff;--verb:#2a2445;--inf:#b4bec2;--infb:#262d30;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#15191b;--card:#1d2326;--fg:#e5e9e9;--mut:#9ba6aa;--line:#323b3f;--acc:#f0c030;--acc2:#f0c030;--sel:#2b2a1c;
--ok:#7fcf9c;--okb:#173323;--at:#f0c030;--atb:#3a3112;--no:#f29a85;--nob:#3d1d16;--ver:#b6a8ff;--verb:#2a2445;--inf:#b4bec2;--infb:#262d30;color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 var(--f)}
.wrap{max-width:1280px;margin:0 auto;padding-block:24px 60px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));display:grid;gap:20px}
header{border-left:6px solid var(--acc);padding-left:14px;display:grid;gap:4px}
.eb{font:12px var(--m);letter-spacing:.06em;text-transform:uppercase;color:var(--mut)}
h1{margin:0;font-size:clamp(22px,3.4vw,30px);line-height:1.15;text-wrap:balance}
.sub{color:var(--mut);max-width:80ch;margin:0}
.bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.tab{font:600 13px var(--f);padding:7px 14px;border-radius:999px;border:1px solid var(--line);background:var(--card);color:var(--fg);cursor:pointer}
.tab[aria-pressed="true"]{background:var(--fg);color:var(--bg);border-color:var(--fg)}
button:focus-visible{outline:3px solid var(--acc);outline-offset:2px}
.cols{display:grid;grid-template-columns:minmax(0,1fr) minmax(300px,420px);gap:22px;align-items:start}
.trilha{display:grid;min-width:0}
.passo{display:grid;grid-template-columns:24px 1fr;gap:10px}
.eixo{display:flex;flex-direction:column;align-items:center}
.pino{width:12px;height:12px;border-radius:50%;background:var(--line);margin-top:20px;flex:none}
.passo.cur .pino{background:var(--acc)}
.fio{flex:1;width:2px;background:var(--line);margin-top:4px}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 14px;margin-bottom:12px;display:grid;gap:8px;min-width:0;cursor:pointer}
.card.cur{background:var(--sel);border-color:var(--acc);box-shadow:0 0 0 1px var(--acc)}
.q{font-weight:600;font-size:16px;text-wrap:balance}
.ref{font:12.5px var(--m);color:var(--acc2)}
.nota{font-size:13.5px;color:var(--mut)}
.ops{display:flex;flex-wrap:wrap;gap:8px}
.op{font:14px var(--f);text-align:left;padding:7px 12px;border-radius:6px;border:1px solid var(--line);background:transparent;color:var(--fg);cursor:pointer;max-width:100%}
.op:hover{border-color:var(--acc)}
.op.sel{background:var(--acc);border-color:var(--acc);color:#1e1a00;font-weight:600}
.op.out{opacity:.45}
.st{font:600 11px var(--m);letter-spacing:.06em;text-transform:uppercase;padding:2px 8px;border-radius:4px;justify-self:start}
.s-ok{background:var(--okb);color:var(--ok)}.s-atencao{background:var(--atb);color:var(--at)}.s-proibido{background:var(--nob);color:var(--no)}
.s-verificar{background:var(--verb);color:var(--ver)}.s-info{background:var(--infb);color:var(--inf)}
.res.c-ok{border-left:4px solid var(--ok)}.res.c-atencao{border-left:4px solid var(--at)}.res.c-proibido{border-left:4px solid var(--no)}.res.c-verificar{border-left:4px solid var(--ver)}
.mais{font:12px var(--m);color:var(--acc2);justify-self:end}
.fim{font:13px var(--m);color:var(--mut)}
/* painel */
.painel{position:sticky;top:12px;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;display:grid;gap:14px;max-height:calc(100vh - 24px);overflow:auto;min-width:0}
.painel .cab{display:grid;gap:4px;border-bottom:1px solid var(--line);padding-bottom:10px}
.painel .tt{font-weight:700;font-size:16px;text-wrap:balance}
.alerta{background:var(--atb);color:var(--at);border-radius:6px;padding:8px 12px;font-size:13.5px;font-weight:600}
.alerta.no{background:var(--nob);color:var(--no)}
.nums{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:8px}
.num{background:var(--bg);border-radius:8px;padding:10px 12px;display:grid;gap:2px}
.num b{font-size:22px;line-height:1.1;font-variant-numeric:tabular-nums}
.num span{font-size:12px;color:var(--mut)}
.bloco{display:grid;gap:6px}
.bloco h3{margin:0;font:600 12px var(--m);letter-spacing:.06em;text-transform:uppercase;color:var(--mut)}
.bloco ul{margin:0;padding-left:18px;font-size:14px;display:grid;gap:4px}
.bloco .tw{overflow-x:auto}
.bloco table{border-collapse:collapse;font-size:13px;width:100%}
.bloco th,.bloco td{text-align:left;padding:4px 8px;border-bottom:1px solid var(--line);vertical-align:top;font-variant-numeric:tabular-nums}
.bloco th{font-family:var(--m);font-size:11px;color:var(--mut);font-weight:600}
.lat{display:grid;gap:8px;border-top:1px dashed var(--line);padding-top:10px}
.lat h3{margin:0;font:600 12px var(--m);letter-spacing:.06em;text-transform:uppercase;color:var(--acc2)}
.lat .card{cursor:default;margin:0;padding:10px 12px}
.lat .card.cur{background:var(--card);border-color:var(--line);box-shadow:none}
.vazio{color:var(--mut);font-size:14px}
/* mapa e lacunas */
.mapa{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px;overflow-x:auto}
.mapa ul{list-style:none;margin:0;padding-left:22px;border-left:1px dashed var(--line)}
.mapa>ul{border:0;padding-left:0}
.mapa li{margin:6px 0}
.tn{display:inline-flex;gap:8px;align-items:baseline;flex-wrap:wrap;font:14px var(--f);text-align:left;background:transparent;border:1px solid var(--line);border-radius:6px;padding:5px 10px;color:var(--fg);cursor:pointer;max-width:100%}
.tn .seta{font:12px var(--m);color:var(--mut);width:1em}
.lbl{font:12px var(--m);color:var(--acc2);margin-right:6px}
.lac{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px 16px 14px 36px;margin:0;display:grid;gap:6px}
h2{margin:0;font-size:19px}
@media (max-width:860px){.cols{grid-template-columns:1fr}.painel{position:static;max-height:none}}
@media (prefers-reduced-motion:no-preference){.card{animation:in .18s ease-out}@keyframes in{from{opacity:.4;transform:translateY(4px)}to{opacity:1;transform:none}}}
</style></head><body>
<div class="wrap">
<header><span class="eb" id="eb"></span><h1 id="tt"></h1><p class="sub" id="st"></p></header>
<div class="bar">
<button class="tab" id="bt-t" aria-pressed="true">Roteiro</button>
<button class="tab" id="bt-m" aria-pressed="false">Mapa</button>
<button class="tab" id="bt-r">Recomeçar</button>
</div>
<section id="v-t" class="cols"><div class="trilha" id="trilha"></div><aside class="painel" id="painel"></aside></section>
<section id="v-m" hidden><div class="mapa" id="mapa"></div></section>
<section id="v-l" hidden><h2>Lacunas e pontos a confirmar no SIGA</h2><ol class="lac" id="lac"></ol></section>
</div>
<script>
const D=__DADOS__;
const N=D.nos, ROT={ok:"permitido",atencao:"com condição",proibido:"não permitido",verificar:"verificar com a concessionária",info:"informação"};
const $=s=>document.getElementById(s);
const el=(t,c,x)=>{const e=document.createElement(t);if(c)e.className=c;if(x!=null)e.textContent=x;return e};
const temDet=n=>n.alerta||n.numeros.length||n.info.length||n.laterais.length;
$("eb").textContent=[D.projeto.fonte,D.projeto.revisao].filter(Boolean).join(" · ");
$("tt").textContent=D.projeto.titulo||"Árvore de decisão";document.title=D.projeto.titulo||document.title;
$("st").textContent=D.projeto.subtitulo||"";
let esc=[], sel=null, lat={};
function caminho(escolhas,inicio){const p=[];let id=inicio,i=0,g=0;while(id&&g++<500){p.push(id);const n=N[id];
 if(n.tipo==="pergunta"){const k=escolhas[i++];if(k==null)break;id=n.opcoes[k].vai}else id=n.segue||null}return p}
function cartao(n,qi,escolhas,aoEscolher,aoSel,ativo){const c=el("div","card"+(n.tipo==="resultado"?" res c-"+n.status:"")+(ativo?" cur":""));
 if(n.tipo==="resultado")c.append(el("span","st s-"+n.status,ROT[n.status]));
 c.append(el("div","q",n.texto));
 if(n.ref)c.append(el("div","ref",n.ref));
 if(n.nota)c.append(el("div","nota",n.nota));
 if(n.tipo==="pergunta"){const o=el("div","ops");n.opcoes.forEach((op,k)=>{const b=el("button","op",op.texto);
  const s=escolhas[qi];if(s!=null){b.classList.add(s===k?"sel":"out")}b.setAttribute("aria-pressed",s===k);
  b.onclick=e=>{e.stopPropagation();aoEscolher(qi,k)};o.append(b)});c.append(o)}
 if(aoSel&&temDet(n)){c.append(el("span","mais","detalhes ▸"));c.onclick=()=>aoSel()}
 else if(aoSel)c.onclick=()=>aoSel();
 return c}
function tra(rolar){const t=$("trilha");t.textContent="";const p=caminho(esc,D.inicio);let qi=0;
 if(sel==null||sel>=p.length)sel=p.length-1;
 const sid=p[sel];
 p.forEach((id,i)=>{const n=N[id];const r=el("div","passo"+(i===sel?" cur":"")),e=el("div","eixo");e.append(el("span","pino"));if(i<p.length-1)e.append(el("span","fio"));
  const idx=i,q=qi;const c=cartao(n,q,esc,(qq,k)=>{esc=esc.slice(0,qq);esc[qq]=k;const np=caminho(esc,D.inicio);sel=np.length-1;for(let j=idx+1;j<np.length;j++){if(temDet(N[np[j]])){sel=j;break}}tra(true)},()=>{sel=idx;tra(false);if(innerWidth<=860)$("painel").scrollIntoView({behavior:"smooth",block:"start"})},i===sel);
  if(n.tipo==="pergunta")qi++;r.append(e,c);t.append(r)});
 const u=N[p[p.length-1]];if(u.tipo==="resultado"&&!u.segue){t.lastChild.lastChild.append(el("div","fim","Fim do roteiro."))}
 painel(N[p[sel]]);
 if(rolar){const cs=t.querySelectorAll(".card");cs[Math.min(sel+1,cs.length-1)].scrollIntoView({behavior:"smooth",block:"nearest"})}}
function blocos(n,dest){
 if(n.alerta)dest.append(el("div","alerta"+(n.status==="proibido"?" no":""),n.alerta));
 if(n.numeros.length){const g=el("div","nums");n.numeros.forEach(x=>{const d=el("div","num");d.append(el("b",null,x.valor),el("span",null,x.rotulo));g.append(d)});dest.append(g)}
 n.info.forEach(b=>{const d=el("div","bloco");if(b.titulo)d.append(el("h3",null,b.titulo));
  if(b.tabela){const w=el("div","tw"),tb=el("table");b.tabela.forEach((lin,i)=>{const tr=el("tr");lin.forEach(c=>tr.append(el(i?"td":"th",null,c)));tb.append(tr)});w.append(tb);d.append(w)}
  else{const u=el("ul");b.itens.forEach(x=>u.append(el("li",null,x)));d.append(u)}
  dest.append(d)})}
function painel(n){const p=$("painel");p.textContent="";
 const cab=el("div","cab");cab.append(el("span","eb",n.tipo==="pergunta"?"pergunta":ROT[n.status]));cab.append(el("div","tt",n.texto));if(n.ref)cab.append(el("div","ref","SIGA "+n.ref));p.append(cab);
 blocos(n,p);
 n.laterais.forEach(lid=>{const box=el("div","lat");box.append(el("h3",null,"Pergunta lateral"));
  const ch=lat[lid]||(lat[lid]=[]);const cam=caminho(ch,lid);let qi=0;
  cam.forEach((id,i)=>{const m=N[id];const q=qi;const c=cartao(m,q,ch,(qq,k)=>{lat[lid]=ch.slice(0,qq);lat[lid][qq]=k;painel(n)},null,false);
   if(m.tipo==="pergunta")qi++;box.append(c);if(m.tipo==="resultado"){const sub=el("div","bloco");blocos(m,sub);if(sub.childNodes.length)box.append(sub)}});
  p.append(box)});
 if(!temDet(n))p.append(el("p","vazio","Sem detalhes adicionais para este passo. Clique em um cartão com \"detalhes\" para ver a ficha."))}
function ramo(id,rot){const li=el("li"),n=N[id],b=el("button","tn");const s=el("span","seta");
 const temf=n.tipo==="pergunta"||n.segue||n.laterais.length;s.textContent=temf?"▸":"";
 if(rot)b.append(el("span","lbl",rot));b.append(s,el("span",null,n.texto));
 if(n.tipo==="resultado")b.append(el("span","st s-"+n.status,ROT[n.status]));
 if(n.ref)b.title=n.ref;li.append(b);
 if(temf){let ab=false,ul=null;b.setAttribute("aria-expanded","false");b.onclick=()=>{ab=!ab;b.setAttribute("aria-expanded",ab);s.textContent=ab?"▾":"▸";
  if(ab){ul=el("ul");if(n.tipo==="pergunta")n.opcoes.forEach(o=>ul.append(ramo(o.vai,o.texto)));else if(n.segue)ul.append(ramo(n.segue,""));
   n.laterais.forEach(l=>ul.append(ramo(l,"lateral")));li.append(ul)}
  else if(ul){ul.remove();ul=null}}}
 return li}
function mapa(){const m=$("mapa");m.textContent="";const u=el("ul");u.append(ramo(D.inicio,""));m.append(u)}
function ver(v){$("v-t").hidden=v!=="t";$("v-m").hidden=v!=="m";$("bt-t").setAttribute("aria-pressed",v==="t");$("bt-m").setAttribute("aria-pressed",v==="m")}
$("bt-t").onclick=()=>ver("t");$("bt-m").onclick=()=>ver("m");$("bt-r").onclick=()=>{esc=[];sel=null;lat={};tra();mapa();ver("t")};
if(D.lacunas.length){$("v-l").hidden=false;D.lacunas.forEach(x=>$("lac").append(el("li",null,x)))}
tra();mapa();
</script></body></html>
"""


def pagina(m):
    dados = json.dumps(m.json(), ensure_ascii=False).replace("</", "<\\/")
    titulo = html.escape(str(m.projeto.get("titulo") or "Árvore de decisão"))
    return PAGINA.replace("__TITULO__", titulo).replace("__DADOS__", dados)


# ---------------------------------------------------------------- main
def etapa(i, t, msg):
    print(f"[{i}/{t}] {msg}")


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 1
    entrada = args[0]
    saida = os.path.dirname(os.path.abspath(entrada))
    if "--saida" in args:
        saida = args[args.index("--saida") + 1]
    os.makedirs(saida, exist_ok=True)
    base = os.path.join(saida, os.path.splitext(os.path.basename(entrada))[0])
    T = 3
    print("=" * 60)
    print(f"GERADOR DE ÁRVORE DE DECISÃO  v{VERSAO}  -  PROLUX Engenharia")
    print("=" * 60)
    etapa(1, T, f"lendo {os.path.basename(entrada)}")
    with open(entrada, encoding="utf-8") as fp:
        cfg = yaml.safe_load(fp)
    m = Modelo(cfg)
    n_p = sum(1 for n in m.nos.values() if n.get("opcoes"))
    n_l = sum(len(n.get("laterais") or []) for n in m.nos.values())
    etapa(2, T, f"gravando HTML ({n_p} perguntas, {len(m.nos) - n_p} resultados, {n_l} laterais)")
    with open(base + ".html", "w", encoding="utf-8") as fp:
        fp.write(pagina(m))
    etapa(3, T, "gravando Mermaid")
    if "--sem-mermaid" not in args:
        with open(base + ".mmd", "w", encoding="utf-8") as fp:
            fp.write(mermaid(m))
    print("-" * 60)
    print(f"HTML: {base}.html")
    if m.avisos:
        print("AVISOS:")
        for a in m.avisos:
            print(f"  - {a}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ErroEntrada as e:
        print(f"ERRO NA ENTRADA: {e}")
        sys.exit(2)
    except yaml.YAMLError as e:
        print(f"ERRO DE SINTAXE NO YAML: {e}")
        sys.exit(2)
