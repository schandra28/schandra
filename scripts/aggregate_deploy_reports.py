#!/usr/bin/env python3
"""Combine deploy report JSON files in <dir>/reports into <dir>/components.json."""
import json,glob,sys,collections
S = sys.argv[1]
comps={}  # (type,name)->info
for f in glob.glob(S+"/reports/*.json"):
    d=json.load(open(f))["result"]
    c=d["details"].get("componentSuccesses",[]); c=c if isinstance(c,list) else [c]
    for x in c:
        t=x.get("componentType"); n=x.get("fullName")
        if not t or n=="package.xml": continue
        k=(t,n); e=comps.setdefault(k,{"deploys":set(),"users":set(),"last":"","deleted":False,"created":False,"file":x.get("fileName")})
        e["deploys"].add(d["id"]); e["users"].add(d["createdByName"])
        if d["createdDate"]>e["last"]:
            e["last"]=d["createdDate"]; e["deleted"]=bool(x.get("deleted")) 
        e["created"]|=bool(x.get("created"))
json.dump([{"type":k[0],"name":k[1],"deploys":sorted(v["deploys"]),"users":sorted(v["users"]),"last":v["last"],"deleted":v["deleted"],"created":v["created"],"file":v["file"]} for k,v in sorted(comps.items())],open(S+"/components.json","w"),indent=1)
cnt=collections.Counter(k[0] for k in comps)
print(len(comps),"unique components;",sum(v["deleted"] for v in comps.values()),"deleted")
for t,n in cnt.most_common(): print(f"{n:5} {t}")
print("users:",collections.Counter(u for v in comps.values() for u in v["users"]))
