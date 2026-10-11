"""Täglicher Abgleich: WebUntis (Klasse BSc PFL 26 BB Basel) -> bfh-lektionen.ics.
Aufruf: python3 tools/sync.py [--init] ; schreibt Änderungen nach changes.txt (leer = keine)."""
import sys, os, json, datetime, re
sys.path.insert(0, os.path.dirname(__file__))
from common import *
from match import *
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICS=os.path.join(ROOT,'bfh-lektionen.ics'); BASE=os.path.join(ROOT,'tools','baseline.json')
CAL='Lektionen'
IGNORE_SUBJ={'DiLe','PA1','BEH'}   # Distance-Learning-Duplikate, Mentoring, Praxis A1 (erlassen), Folgesemester
END=datetime.date(2027,2,14)                  # Ende HS26
SUBJNAME={'SBG_MTR':'Studienbegleitung','PRO':'Prof. Pflege','KA1':'KA 1','DST':'Statistik','IFS':'Inferenzstatistik','GÖP':'GÖP','TE1':'Englisch','BSC_PFL':'BFH'}
CATNAME={'SBG_MTR':'Studienbegleitung','PRO':'Professionelle Pflege','KA1':'Klinisches Assessment 1','DST':'Deskriptive Statistik','IFS':'Inferenzstatistik','GÖP':'Gesundheitsökonomie und Gesundheitspolitik','TE1':'Technical English 1','BSC_PFL':'BFH'}
ADDR='BFH Gesundheit\\, Binningerstrasse 2\\, 4142 Münchenstein'
ONLINE='Online (Link auf Moodle / MS Teams)'
def hm(s): return int(s[:2])*60+int(s[2:])
def fmt(m): return f"{m//60:02d}{m%60:02d}"
def dstr(d): return f"{d[6:8]}.{d[4:6]}."
def loc_for(rooms):
    rs=roomstr(rooms)
    if rs: return f"{rs}\\, {ADDR}"
    return ONLINE if rooms else 'Ort noch offen (siehe WebUntis)'
def snap(ps):
    act=[p for p in ps if not p['cancelled']]
    return dict(ids=sorted(p['id'] for p in ps), cancelled=sorted(p['id'] for p in ps if p['cancelled']),
        start=min((p['start'] for p in act),default=None), end=max((p['end'] for p in act),default=None),
        rooms=sorted(set(r for p in act for r in p['rooms'])), lessonIds=sorted(set(p['lessonId'] for p in ps)))
def setf(ev,name,val):
    k,_=key(ev,name)
    if k is None: k=name; ev['order'].insert(len(ev['order']),k)
    ev['fields'][k]=val
def now(): return datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
def new_event(ps):
    p=ps[0]; s=min(x['start'] for x in ps); e=max(x['end'] for x in ps)
    subj=p['subj']; title=p['text'] or subj
    uid=f"bb26-{p['date']}-{s}-wu{p['lessonId']}@bfh-lektionen"
    f={'UID':uid,'DTSTAMP':now(),'DTSTART;TZID=Europe/Zurich':f"{p['date']}T{s}00",'DTEND;TZID=Europe/Zurich':f"{p['date']}T{e}00",
       'SUMMARY':esc(f"{SUBJNAME.get(subj,subj)}: {title}"),'LOCATION':loc_for(sorted(set(r for x in ps for r in x['rooms']))),
       'DESCRIPTION':esc(f"Modul: {CATNAME.get(subj,subj)}\nAus WebUntis übernommen (automatisch)."),'CATEGORIES':esc(CATNAME.get(subj,subj)),'TRANSP':'OPAQUE'}
    return dict(fields=f,order=list(f.keys()))
def main(init=False, raw=None):
    today=datetime.date.today()
    weeks=json.load(open(raw)) if raw else fetch(today-datetime.timedelta(days=1), END)
    P=periods(weeks)
    head,evs=parse_ics(open(ICS,encoding='utf-8').read())
    base=json.load(open(BASE)) if os.path.exists(BASE) and not init else {'events':{},'known':[],'mine':[]}
    tod=today.strftime('%Y%m%d'); changes=[]
    fetched_from=min(P[k]['date'] for k in P) if P else tod
    known=set(base.get('known',[])); mine=set(base.get('mine',[]))
    covered=set()
    for ev in evs:
        _,uid=key(ev,'UID'); d,st,en,s,loc=ev_info(ev)
        if 'ABGABE' in s or not st: continue
        b=base['events'].get(uid)
        if init or b is None:
            m=match(ev,P)
            if not m: continue
            base['events'][uid]=snap(m); known|=set(x['id'] for x in m); mine|=set(x['lessonId'] for x in m); covered|=set(x['id'] for x in m); continue
        if d<tod: covered|=set(b['ids']); continue
        ps=[P[str(i)] for i in b['ids'] if str(i) in P]
        covered|=set(b['ids'])
        if len(ps)<len(b['ids']) and d>=fetched_from:
            gone=[i for i in b['ids'] if str(i) not in P]
            for i in gone: ps.append(dict(id=i,cancelled=True,start=None,end=None,rooms=[],lessonId=None))
        n=snap(ps); clean=s.replace('ENTFÄLLT: ','')
        label=f"{dstr(d)} {clean.replace(chr(92),'')}"
        if len(n['cancelled'])==len(n['ids']) and len(b['cancelled'])<len(b['ids']):
            setf(ev,'SUMMARY','ENTFÄLLT: '+clean); changes.append(f"ENTFÄLLT: {label}")
        elif len(n['cancelled'])<len(n['ids']) and 'ENTFÄLLT: ' in s:
            setf(ev,'SUMMARY',clean)
            changes.append(f"Findet doch statt: {label}")
        elif n['cancelled']!=b['cancelled'] and n['cancelled']:
            changes.append(f"Teilweise abgesagt: {label} (WebUntis prüfen)")
        if n['start'] and b['start'] and (n['start'],n['end'])!=(b['start'],b['end']):
            k1,v1=key(ev,'DTSTART');k2,v2=key(ev,'DTEND')
            ns=hm(v1[9:13])+hm(n['start'])-hm(b['start']); ne=hm(v2[9:13])+hm(n['end'])-hm(b['end'])
            ev['fields'][k1]=v1[:9]+fmt(ns)+'00'; ev['fields'][k2]=v2[:9]+fmt(ne)+'00'
            changes.append(f"Neue Zeit: {label}: {fmt(ns)[:2]}:{fmt(ns)[2:]}–{fmt(ne)[:2]}:{fmt(ne)[2:]}")
        if n['start'] and set(n['rooms'])!=set(b['rooms']):
            setf(ev,'LOCATION',loc_for(n['rooms']))
            changes.append(f"Neuer Raum: {label}: {roomstr(n['rooms']) or 'online'}")
        if n!=b:
            setf(ev,'DTSTAMP',now()); base['events'][uid]=n
    # neue Lektionen
    cand=[p for p in P.values() if p['id'] not in known and p['id'] not in covered and p['date']>=tod and p['date']<=END.strftime('%Y%m%d')
          and p['subj'] not in IGNORE_SUBJ and not OTHER.search(p)]
    groups={}
    for p in cand: groups.setdefault((p['date'],p['subj'],p['text']),[]).append(p)
    for (d,_s,_t),ps in sorted(groups.items()):
        lid=ps[0]['lessonId']
        if init: continue
        ev=new_event(ps); evs.append(ev); _,uid=key(ev,'UID'); base['events'][uid]=snap(ps)
        known|=set(p['id'] for p in ps)
        hint='' if any(p['lessonId'] in mine for p in ps) else ' (neue Lektion, bitte prüfen, ob sie deine Gruppe betrifft)'
        changes.append(f"NEU: {dstr(d)} {SUBJNAME.get(ps[0]['subj'],ps[0]['subj'])}: {ps[0]['text']} {min(p['start'] for p in ps)[:2]}:{min(p['start'] for p in ps)[2:]}{hint}")
    base['known']=sorted(known|covered); base['mine']=sorted(mine)
    evs.sort(key=lambda e:(key(e,'DTSTART')[1] or ''))
    open(ICS,'w',encoding='utf-8',newline='').write(write_ics(head,evs,CAL))
    json.dump(base,open(BASE,'w'),indent=0)
    import common
    if common.MAPPING is None: changes.append('Hinweis: Schlüssel tools/lehrpersonen.json fehlt, Namen wurden durch «Lehrperson neu» ersetzt.')
    for n in sorted(common.UNKNOWN): changes.append(f'Neue Lehrperson in WebUntis: {n} (bitte Nummer im Schlüssel ergänzen).')
    open(os.path.join(ROOT,'changes.txt'),'w').write('\n'.join(changes))
    print('\n'.join(changes) if changes else 'Keine Änderungen.')
if __name__=='__main__':
    raw=None
    if '--raw' in sys.argv: raw=sys.argv[sys.argv.index('--raw')+1]
    main(init='--init' in sys.argv, raw=raw)
