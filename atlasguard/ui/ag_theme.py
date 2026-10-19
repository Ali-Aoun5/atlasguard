"""AtlasGuard visual system.

Identity: a floating navy dock over a cool paper canvas.  Security status is the
only strong colour on the page:  green = clear,  amber = check,  red = blocked,
and every status always carries a one-sentence reason.
The memorable element is the Payment Journey: five checkpoints a payment passes.
"""
import html

import streamlit as st

COL = {"green": "#0E9F6E", "amber": "#C77700", "red": "#D6334A", "idle": "#8A94AD"}
SOFT = {"green": "#E3F6EE", "amber": "#FFF2D6", "red": "#FDE6EA", "idle": "#EEF1F7"}
WORD = {"green": "Clear", "amber": "Check", "red": "Blocked", "idle": "Waiting"}
ICON = {"green": "✓", "amber": "!", "red": "✕", "idle": "·"}

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@500;600;700&family=Figtree:wght@400;500;600;700&family=JetBrains+Mono:wght@500&display=swap');
:root{--bg:#EBEEF5;--card:#fff;--ink:#0A1630;--muted:#59647F;--line:#DCE1EE;--brand:#3547F5;--brand2:#6A4DFF;
--navy:#0A1630;--navy2:#142349}
html,body,.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"]{background:var(--bg)!important}
.stApp{color:var(--ink);font-family:'Figtree',system-ui,sans-serif}
.stApp p,.stApp li,.stApp label,.stApp small{font-family:'Figtree',system-ui,sans-serif}
.stApp [data-testid="stMarkdownContainer"],.stApp [data-testid="stMarkdownContainer"] p,
.stApp [data-testid="stWidgetLabel"],.stApp [data-testid="stWidgetLabel"] p,
.stApp [data-testid="stCaptionContainer"],.stApp [data-testid="stMetricLabel"]{color:var(--ink)}
.stApp [data-testid="stCaptionContainer"],.stApp [data-testid="stCaptionContainer"] p{color:var(--muted)}
.stApp h1,.stApp h2,.stApp h3,.stApp h4{font-family:'Sora',sans-serif;color:var(--ink);letter-spacing:-.015em}
header[data-testid="stHeader"],[data-testid="stSidebar"],[data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"],[data-testid="stToolbar"],[data-testid="stDecoration"],
footer,#MainMenu{display:none!important}
.block-container{max-width:1280px;padding:14px 28px 96px 28px!important}
[data-testid="stVerticalBlock"]{gap:1rem}

/* ============ dock (top bar) ============ */
[data-testid="stHorizontalBlock"]:has(.ag-dock){position:sticky;top:10px;z-index:60;align-items:center;
 background:linear-gradient(120deg,#0A1630 0%,#142349 100%);border-radius:22px;padding:10px 14px 10px 20px;
 box-shadow:0 14px 40px rgba(10,22,48,.28);margin-bottom:26px;gap:.5rem}
.ag-brand{display:flex;align-items:center;gap:12px;color:#fff}
.ag-brand b{font-family:'Sora',sans-serif;font-size:1.12rem;letter-spacing:-.01em;color:#fff}
.ag-brand small{display:block;color:#9FB0DA;font-size:.72rem;margin-top:1px}
[data-testid="stHorizontalBlock"]:has(.ag-dock) [data-testid="stRadio"] [role="radiogroup"]{justify-content:center;gap:4px;flex-wrap:nowrap}
[data-testid="stHorizontalBlock"]:has(.ag-dock) label[data-baseweb="radio"]{background:transparent;border:0;padding:9px 18px;border-radius:14px}
[data-testid="stHorizontalBlock"]:has(.ag-dock) label[data-baseweb="radio"] *{color:#C5D0EE!important;font-weight:600;font-size:.95rem}
[data-testid="stHorizontalBlock"]:has(.ag-dock) label[data-baseweb="radio"]:hover{background:rgba(255,255,255,.08)}
[data-testid="stHorizontalBlock"]:has(.ag-dock) label[data-baseweb="radio"]:has(input:checked){background:#fff;box-shadow:0 4px 14px rgba(0,0,0,.25)}
[data-testid="stHorizontalBlock"]:has(.ag-dock) label[data-baseweb="radio"]:has(input:checked) *{color:var(--ink)!important}
[data-testid="stHorizontalBlock"]:has(.ag-dock) .stButton button{background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.22);color:#fff;border-radius:12px;min-height:38px}
[data-testid="stHorizontalBlock"]:has(.ag-dock) .stButton button *{color:#fff!important}
.ag-dockstate{display:flex;justify-content:flex-end;gap:8px;flex-wrap:wrap}
.ag-dockchip{display:inline-flex;align-items:center;gap:7px;color:#DCE5FF;font-size:.8rem;font-weight:600;
 padding:6px 12px;border-radius:999px;background:rgba(255,255,255,.09)}
.ag-dot{width:8px;height:8px;border-radius:50%;display:inline-block}

/* ============ radios outside the dock = selectable chips / list rows ============ */
[data-testid="stRadio"] [role="radiogroup"]{gap:8px}
label[data-baseweb="radio"]{background:#fff;border:1px solid var(--line);border-radius:12px;padding:9px 14px;margin:0;cursor:pointer;transition:border-color .15s}
label[data-baseweb="radio"]>div:first-child{display:none!important}
label[data-baseweb="radio"] *{color:var(--ink)!important;font-weight:600}
label[data-baseweb="radio"]:has(input:checked){border-color:var(--brand);box-shadow:0 0 0 3px rgba(53,71,245,.14)}
label[data-baseweb="radio"]:hover{border-color:#B9C2DD}

/* ============ page head ============ */
.ag-pagehead{margin:4px 0 20px 0}
.ag-pagehead h1{margin:0;font-size:2.15rem;font-weight:700;line-height:1.1}
.ag-pagehead p{margin:8px 0 0 0;color:var(--muted);font-size:1.02rem;max-width:62ch;line-height:1.5}

/* ============ surfaces ============ */
[data-testid="stVerticalBlockBorderWrapper"]{background:var(--card);border:1px solid var(--line)!important;
 border-radius:20px!important;box-shadow:0 1px 2px rgba(10,22,48,.04),0 10px 28px rgba(10,22,48,.05);padding:6px 8px}
.ag-h{font-family:'Sora',sans-serif;font-weight:600;font-size:1.05rem;margin:2px 0 4px 0;color:var(--ink)}
.ag-sub{color:var(--muted);font-size:.9rem;line-height:1.45;margin-bottom:8px}
.ag-num{font-family:'Sora',sans-serif;font-weight:700;letter-spacing:-.02em;color:var(--ink)}
.ag-mono{font-family:'JetBrains Mono',monospace;font-size:.82rem}
.ag-muted{color:var(--muted)}

/* ============ status ============ */
.ag-chip{display:inline-flex;align-items:center;gap:6px;padding:4px 11px;border-radius:999px;font-weight:700;font-size:.78rem;white-space:nowrap}
.ag-status{display:flex;gap:14px;align-items:flex-start;padding:14px 16px;border-radius:16px;margin:6px 0;border:1px solid}
.ag-status .ic{flex:0 0 34px;height:34px;border-radius:50%;display:flex;align-items:center;justify-content:center;
 color:#fff;font-weight:800;font-size:1rem}
.ag-status .tt{font-family:'Sora',sans-serif;font-weight:600;font-size:1rem}
.ag-status .rs{color:#2A3553;line-height:1.45;margin-top:2px}

/* ============ journey ============ */
.ag-journey{display:flex;gap:0;align-items:flex-start;padding:6px 4px 2px 4px}
.ag-jstep{flex:1;min-width:0;position:relative;padding:0 10px;text-align:left}
.ag-jstep:not(:last-child):after{content:'';position:absolute;top:17px;left:calc(34px + 14px);right:-4px;height:3px;border-radius:3px;background:var(--line)}
.ag-jstep.done:not(:last-child):after{background:var(--lc)}
.ag-jnode{width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:800;
 color:#fff;background:var(--lc);position:relative;z-index:2;box-shadow:0 0 0 5px var(--ls)}
.ag-jstep .jt{font-family:'Sora',sans-serif;font-weight:600;font-size:.92rem;margin-top:12px}
.ag-jstep .jr{color:var(--muted);font-size:.82rem;line-height:1.4;margin-top:3px;padding-right:6px}
@media(max-width:900px){.ag-journey{flex-direction:column;gap:14px}.ag-jstep:after{display:none!important}}

/* ============ tiles / lists ============ */
.ag-tile{min-height:112px;border-radius:16px;padding:14px 16px;border:1px solid var(--line);background:#fff;height:100%}
.ag-tile .k{color:var(--muted);font-size:.82rem;font-weight:600}
.ag-tile .v{font-family:'Sora',sans-serif;font-weight:700;font-size:1.7rem;margin-top:4px;letter-spacing:-.02em}
.ag-row{display:flex;gap:12px;align-items:center;padding:12px 4px;border-bottom:1px solid var(--line)}
.ag-row:last-child{border-bottom:0}
.ag-row .av{flex:0 0 38px;height:38px;border-radius:12px;background:#EEF1FA;display:flex;align-items:center;justify-content:center;
 font-family:'Sora',sans-serif;font-weight:700;color:var(--brand)}
.ag-row .tx{flex:1;min-width:0}.ag-row .t1{font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ag-row .t2{color:var(--muted);font-size:.82rem}
.ag-row .am{font-family:'JetBrains Mono',monospace;font-size:.9rem;font-weight:500;text-align:right}
.ag-route{border:1px solid var(--line);border-radius:16px;padding:14px 16px;background:#fff;height:100%}
.ag-route.best{border-color:var(--ok,#0E9F6E);box-shadow:0 0 0 3px rgba(14,159,110,.14)}
.ag-route .pn{font-family:'Sora',sans-serif;font-weight:600}
.ag-route .tot{font-family:'Sora',sans-serif;font-weight:700;font-size:1.35rem;margin:6px 0 4px 0}
.ag-route .ft{color:var(--muted);font-size:.84rem;line-height:1.5}

/* ledger bar */
.ag-ledger{display:flex;height:16px;border-radius:999px;overflow:hidden;background:#E3E8F4;margin:10px 0 8px 0}
.ag-ledger .a{background:var(--brand)}.ag-ledger .b{background:#0E9F6E}.ag-ledger .c{background:#D6334A}
.ag-legend{display:flex;gap:18px;flex-wrap:wrap;color:var(--muted);font-size:.86rem}
.ag-legend i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px}

/* trace */
.ag-trace{border-left:3px solid var(--line);margin:6px 0 4px 10px;padding-left:18px}
.ag-tr{position:relative;margin-bottom:14px;font-size:.92rem;line-height:1.4}
.ag-tr:before{content:'';position:absolute;left:-28px;top:3px;width:13px;height:13px;border-radius:50%;background:var(--lc,#8A94AD);border:3px solid #fff}
.ag-tr .k{color:var(--muted);font-size:.78rem;font-weight:600}
.ag-tr code{background:#EEF1FA;color:var(--ink);padding:1px 7px;border-radius:6px;font-size:.84rem}

/* chain */
.ag-chain{display:flex;gap:0;overflow-x:auto;padding:6px 2px 14px 2px}
.ag-block{flex:0 0 168px;border:1px solid var(--line);border-radius:14px;padding:10px 12px;background:#fff;position:relative;margin-right:26px}
.ag-block:not(:last-child):after{content:'';position:absolute;right:-27px;top:50%;width:26px;height:3px;background:var(--lc,#0E9F6E)}
.ag-block .bid{font-family:'Sora',sans-serif;font-weight:700;font-size:.86rem}
.ag-block .bh{font-family:'JetBrains Mono',monospace;font-size:.72rem;color:var(--muted);margin-top:4px;word-break:break-all}
.ag-block .ba{font-size:.8rem;margin-top:4px;font-weight:600}

/* ============ inputs & buttons ============ */
.stApp input,.stApp textarea{color:var(--ink)!important;background:#fff!important}
div[data-baseweb="input"],div[data-baseweb="base-input"],div[data-baseweb="textarea"],div[data-baseweb="select"]>div{
 background:#fff!important;border-color:var(--line)!important;border-radius:12px!important}
div[data-baseweb="select"] *{color:var(--ink)!important}
[data-baseweb="popover"] li,[data-baseweb="popover"] ul{background:#fff!important;color:var(--ink)!important}
.stButton button,.stDownloadButton button{border-radius:12px;font-weight:600;border:1px solid var(--line);background:#fff;color:var(--ink);min-height:42px}
.stButton button *,.stDownloadButton button *{color:inherit!important}
.stButton button:hover,.stDownloadButton button:hover{border-color:var(--brand);color:var(--brand)}
button[kind="primary"],button[data-testid="stBaseButton-primary"]{background:linear-gradient(120deg,var(--brand),var(--brand2))!important;
 border:0!important;color:#fff!important;box-shadow:0 8px 20px rgba(53,71,245,.3)}
button[kind="primary"] *,button[data-testid="stBaseButton-primary"] *{color:#fff!important}
button:disabled{opacity:.45}
[data-testid="stChatInput"]{background:#fff;border:1px solid var(--line);border-radius:16px}
[data-testid="stChatInput"] textarea{color:var(--ink)!important}
[data-testid="stChatMessage"]{background:#fff;border:1px solid var(--line);border-radius:16px;padding:12px 14px}
[data-testid="stChatMessage"] *{color:var(--ink)}
[data-testid="stFileUploaderDropzone"]{background:#F4F6FC;border:1.5px dashed #B9C2DD;border-radius:14px}
[data-testid="stFileUploaderDropzone"] *{color:var(--ink)!important}
[data-testid="stExpander"]{border:1px solid var(--line);border-radius:14px;background:#fff}
[data-testid="stExpander"] *{color:var(--ink)}
.stApp pre,.stApp code{background:#F1F3FA!important;color:var(--ink)!important}
[data-testid="stSlider"] *{color:var(--ink)}
:focus-visible{outline:3px solid rgba(53,71,245,.5)!important;outline-offset:2px}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
@keyframes agflip{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
.ag-flip{animation:agflip .35s ease both}
</style>
"""


def _dual(css: str) -> str:
    """Streamlit changed its radio markup between versions. Style both."""
    out = []
    for line in css.split("\n"):
        out.append(line)
        if 'label[data-baseweb="radio"]' in line:
            out.append(line.replace('label[data-baseweb="radio"]', 'label[data-testid="stRadioOption"]'))
    out.append('<style>label[data-testid="stRadioOption"]>div>div:first-child{display:none!important}'
               'label[data-testid="stRadioOption"]{display:flex}'
               '[data-testid="stRadioGroup"]{gap:8px}</style>')
    return "\n".join(out)


def inject_css() -> None:
    st.markdown(_dual(_CSS), unsafe_allow_html=True)


def e(x) -> str:
    return html.escape(str(x))


def level_of(value, default: str = "amber") -> str:
    v = str(value or "").lower()
    if v in ("green", "amber", "red", "idle"):
        return v
    if v in ("ok", "safe", "pass", "passed", "allow", "allowed", "verified", "executed", "executed_in_sandbox", "clear"):
        return "green"
    if v.startswith(("block", "refus", "reject", "den", "fail")) or v in ("scam",):
        return "red"
    return default


def chip(level: str, text: str = "") -> str:
    lv = level_of(level)
    return (f"<span class='ag-chip' style='background:{SOFT[lv]};color:{COL[lv]}'>"
            f"<span class='ag-dot' style='background:{COL[lv]}'></span>{e(text or WORD[lv])}</span>")


def status(level: str, reason: str, title: str = "") -> None:
    """The one status component: icon, plain-word verdict, and a reason sentence."""
    lv = level_of(level)
    st.markdown(
        f"<div class='ag-status' style='background:{SOFT[lv]};border-color:{COL[lv]}55'>"
        f"<div class='ic' style='background:{COL[lv]}'>{ICON[lv]}</div>"
        f"<div><div class='tt' style='color:{COL[lv]}'>{e(title or WORD[lv])}</div>"
        f"<div class='rs'>{e(reason)}</div></div></div>", unsafe_allow_html=True)


banner = status


def pagehead(title: str, text: str) -> None:
    st.markdown(f"<div class='ag-pagehead'><h1>{e(title)}</h1><p>{e(text)}</p></div>", unsafe_allow_html=True)


def heading(title: str, sub: str = "") -> None:
    st.markdown(f"<div class='ag-h'>{e(title)}</div>" + (f"<div class='ag-sub'>{e(sub)}</div>" if sub else ""),
                unsafe_allow_html=True)


def tile(label: str, value: str, level: str = "", note: str = "") -> str:
    c = f"style='color:{COL[level_of(level)]}'" if level else ""
    n = f"<div class='ag-sub' style='margin:2px 0 0 0'>{e(note)}</div>" if note else ""
    return f"<div class='ag-tile'><div class='k'>{e(label)}</div><div class='v' {c}>{e(value)}</div>{n}</div>"


def journey(steps: list) -> None:
    """steps = [(title, level, reason)] in order. The one memorable element."""
    out = []
    for title, level, reason in steps:
        lv = level_of(level, "idle")
        done = "done" if lv != "idle" else ""
        out.append(
            f"<div class='ag-jstep {done}' style='--lc:{COL[lv]};--ls:{SOFT[lv]}'>"
            f"<div class='ag-jnode'>{ICON[lv]}</div><div class='jt'>{e(title)}</div>"
            f"<div class='jr'>{e(reason)}</div></div>")
    st.markdown("<div class='ag-journey'>" + "".join(out) + "</div>", unsafe_allow_html=True)


def ring(value: int, total: int, level: str, label: str, size: int = 150) -> str:
    lv = level_of(level)
    r, c = 52, 2 * 3.14159 * 52
    frac = (value / total) if total else 0
    return (f"<div style='display:flex;align-items:center;gap:16px'>"
            f"<svg width='{size}' height='{size}' viewBox='0 0 130 130'>"
            f"<circle cx='65' cy='65' r='{r}' fill='none' stroke='#E3E8F4' stroke-width='13'/>"
            f"<circle cx='65' cy='65' r='{r}' fill='none' stroke='{COL[lv]}' stroke-width='13' stroke-linecap='round' "
            f"stroke-dasharray='{c * frac:.1f} {c:.1f}' transform='rotate(-90 65 65)'/>"
            f"<text x='65' y='71' text-anchor='middle' font-family='Sora' font-weight='700' font-size='24' fill='#0A1630'>"
            f"{value}/{total}</text></svg><div class='ag-sub' style='max-width:18ch'>{e(label)}</div></div>")


def ss(key, default):
    if key not in st.session_state:
        st.session_state[key] = default
    return st.session_state[key]


LOGO = ("<svg width='34' height='34' viewBox='0 0 40 40'><defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>"
        "<stop offset='0' stop-color='#7C8BFF'/><stop offset='1' stop-color='#6A4DFF'/></linearGradient></defs>"
        "<rect width='40' height='40' rx='12' fill='url(#g)'/>"
        "<circle cx='20' cy='20' r='9' fill='none' stroke='#fff' stroke-width='2'/>"
        "<ellipse cx='20' cy='20' rx='4' ry='9' fill='none' stroke='#fff' stroke-width='2'/>"
        "<path d='M11 20h18' stroke='#fff' stroke-width='2'/></svg>")
