import re, sys
def pages(f):
    t=open(f,encoding='utf-8',errors='replace').read()
    parts=re.split(r'===PAGE (\d+)===\n', t)
    out={}
    for i in range(1,len(parts),2):
        out[int(parts[i])]=parts[i+1]
    return out
def show(f,kws,maxp=4,width=190):
    mp=pages(f); print('#####',f)
    for kw in kws:
        ps=[p for p in sorted(mp) if re.search(kw,mp[p],re.I)]
        print(' KW %r -> pages %s'%(kw,ps[:24]))
        for p in ps[:maxp]:
            for line in mp[p].split('\n'):
                if re.search(kw,line,re.I):
                    print('   p%-4d %s'%(p,line.strip()[:width])); break
