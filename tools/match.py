import re
from common import *
OTHER_RE=re.compile(r'Gr\. ?1\b|Advanced',re.I)
MENTOR=3974  # WebUntis-Kennung der eigenen Mentorin (Zahl statt Name)
class _Other:
    def search(self,p):
        if isinstance(p,str): return OTHER_RE.search(p)
        return OTHER_RE.search(p['text']) or ('Mentor-Meeting' in p['text'] and MENTOR not in p.get('teachers',[]))
OTHER=_Other()
def ev_info(ev):
    _,ds=key(ev,'DTSTART');_,de=key(ev,'DTEND');_,s=key(ev,'SUMMARY');_,loc=key(ev,'LOCATION')
    return ds[:8],ds[9:13],de[9:13],s,loc or ''
def match(ev,P):
    d,st,en,s,_=ev_info(ev)
    if 'ABGABE' in s or not st: return []
    return [p for p in P.values() if p['date']==d and p['start']<en and st<p['end'] and not OTHER.search(p) and p['subj']!='DiLe']
def roomstr(rooms):
    rs=[r for r in rooms if r and 'Online' not in r]
    if not rs: return None
    pre=rs[0].rsplit(' ',1)[0]
    if all(r.rsplit(' ',1)[0]==pre for r in rs): return pre+' '+' / '.join(r.rsplit(' ',1)[-1] for r in rs)
    return ' / '.join(rs)
