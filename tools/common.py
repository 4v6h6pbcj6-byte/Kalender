import re, json, datetime, urllib.request, http.cookiejar
SUBJ={'PRO':'Prof. Pflege','KA1':'KA 1','DST':'Statistik','IFS':'Inferenzstatistik','GÖP':'GÖP','TE1':'Englisch','BSC_PFL':'BFH','DiLe':None}
CAT2SUBJ={'Professionelle Pflege':'PRO','Klinisches Assessment 1':'KA1','Deskriptive Statistik':'DST','Inferenzstatistik':'IFS','Gesundheitsökonomie und Gesundheitspolitik':'GÖP','Technical English 1':'TE1'}
def fetch(start,end):
    cj=http.cookiejar.CookieJar(); op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    op.open("https://bfh-g.webuntis.com/WebUntis/?school=bfh-g",timeout=30).read()
    d=start-datetime.timedelta(days=start.weekday()); weeks={}
    while d<=end:
        u=f"https://bfh-g.webuntis.com/WebUntis/api/public/timetable/weekly/data?elementType=1&elementId=2312&date={d}&formatId=1"
        weeks[str(d)]=json.loads(op.open(u,timeout=30).read()); d+=datetime.timedelta(days=7)
    return weeks
def periods(weeks):
    el={};P={}
    for v in weeks.values():
        r=v['data']['result']['data']
        for e in r['elements']: el[(e['type'],e['id'])]=e
        for p in r['elementPeriods'].get('2312',[]): P[p['id']]=p
    out={}
    for pid,p in P.items():
        g=lambda t:[ (el.get((t,x['id']),{}).get('name') or el.get((t,x['id']),{}).get('longName')) for x in p['elements'] if x['type']==t]
        go=lambda t:[ (el.get((t,x['orgId']),{}).get('name')) for x in p['elements'] if x['type']==t and x.get('orgId')]
        out[str(pid)]=dict(id=pid,lessonId=p['lessonId'],date=str(p['date']),start=f"{p['startTime']:04d}",end=f"{p['endTime']:04d}",
            subj=(g(3) or [None])[0],text=p['lessonText'],rooms=sorted(set(g(4))),origrooms=sorted(set(go(4))),
            teachers=[x['id'] for x in p['elements'] if x['type']==2],
            cancelled=(p['cellState'] in ('CANCEL','FREE') or p.get('is',{}).get('cancelled',False)),
            state=p['cellState'],substText=p.get('substText',''),periodText=p.get('periodText',''))
    names=sorted({(e.get('longName') or e.get('name') or '') for (t,_),e in el.items() if t==2}-{''},key=len,reverse=True)
    for o in out.values(): o['text']=clean_names(o['text'],names)
    return out
import os as _os
_KEY=_os.path.join(_os.path.dirname(_os.path.abspath(__file__)),'lehrpersonen.json')
MAPPING=json.load(open(_KEY,encoding='utf-8')) if _os.path.exists(_KEY) else None
UNKNOWN=set()
def clean_names(text,names):
    """Namen von Lehrpersonen durch «Lehrperson NN» ersetzen (Datenschutz: im öffentlichen
    Repository stehen keine Namen). Der Schlüssel Name -> Nummer liegt nur privat
    (tools/lehrpersonen.json, nicht im Repository)."""
    for n in names:
        if len(n)<=2: continue
        pat=r'\b'+re.escape(n)+r'\b'
        if re.search(pat,text,flags=re.I):
            nr=(MAPPING or {}).get(n)
            if nr is None: UNKNOWN.add(n)
            text=re.sub(pat,f'Lehrperson {nr}' if nr else 'Lehrperson neu',text,flags=re.I)
    return re.sub(r'\s{2,}',' ',text).strip()
# ICS
def unfold(t): return t.replace('\r\n','\n').replace('\n ','')
def parse_ics(t):
    t=t.replace('\r\n','\n')
    head,_,rest=t.partition('BEGIN:VEVENT')
    blocks=re.findall(r'BEGIN:VEVENT\n(.*?)END:VEVENT\n',t,re.S)
    evs=[]
    for b in blocks:
        b=b.replace('\n ','')
        f={};order=[]
        for l in b.strip('\n').split('\n'):
            k,_,v=l.partition(':'); f[k]=v; order.append(k)
        evs.append(dict(fields=f,order=order))
    return head,evs
def key(ev,name):
    for k,v in ev['fields'].items():
        if k.split(';')[0]==name: return k,v
    return None,None
def esc(s): return s.replace('\\','\\\\').replace(';','\\;').replace(',','\\,').replace('\n','\\n')
def fold(line):
    b=line.encode('utf-8'); out=[];cur=b''
    while len(b)>73:
        cut=73
        while (b[cut]&0xC0)==0x80: cut-=1
        out.append(b[:cut]); b=b[cut:]
    out.append(b)
    return '\r\n '.join(x.decode('utf-8') for x in out)
def write_ics(head,evs,calname):
    head=re.sub(r'X-WR-CALNAME:.*',f'X-WR-CALNAME:{calname}',head.replace('\r\n','\n'))
    lines=[l for l in head.strip('\n').split('\n')]
    for ev in evs:
        lines.append('BEGIN:VEVENT')
        for k in ev['order']: lines.append(f"{k}:{ev['fields'][k]}")
        lines.append('END:VEVENT')
    lines.append('END:VCALENDAR')
    return '\r\n'.join(fold(l) for l in lines)+'\r\n'
