#!/usr/bin/env python3
"""Build dependency-ordered package.xml files from a components inventory.

Input : components.json (list of {type, name, users, deploys, last, ...}) built
        from the target org's successful, non-validation DeployRequest history.
Output: manifest/prod-release/NN-<stage>.xml plus inventory.csv.
"""
import csv, json, os, sys
from collections import defaultdict

API = "68.0"
inv_path, out_dir = sys.argv[1], sys.argv[2]
comps = json.load(open(inv_path))

DLM = lambda n: "__dlm" in n.split(".")[0] or n.startswith("ssot__")
SYSTEM_USER = "Automated Process"
# Test/demo survey flows, plus Account_Segment_Update which is an InvalidDraft in lscqa.
REVIEW_FLOWS = {"cb_survey_test_1", "cb_survey_test_2_mobile", "survey_for_demo_2", "survey_for_demo_29_10",
                "Account_Segment_Update"}
CUSTOM_OBJ = lambda n: n.endswith("__c")
# Launcher flows call a BatchProcessJobDefinition, which in turn calls a worker
# flow, so they must deploy after 04-batch-jobs.
BATCH_LAUNCHER_FLOWS = {"AL_Copying_of_HCO_address_to_HCP", "AL_Sequence_Address_Batch_Job",
                        "AL_Run_Account_Summarization_Batch_Job"}
# Deployed earlier but no longer present in the source org (renamed/deleted);
# confirmed by a retrieve from lscqa returning "cannot be found".
GONE = {("Profile", "AL Field Sales Representative"),
        ("DataKitObjectTemplate", "STGTransform1"),
        ("DataPackageKitObject", "DataLoad_INT_QA_Package2_1794402693583")}

# (file, title, predicate) in deploy order. First match wins.
STAGES = [
 ("00-org-settings", "Org settings that must be on before the site can deploy",
   lambda t, n: t == "ExperienceBundleSettings"),
 ("01-schema", "Value sets, objects, fields, labels, static resources, notification types, email templates, credentials",
   lambda t, n: (t in ("CustomObject", "CustomField") and not DLM(n)) or t in (
     "StandardValueSet", "CustomLabel", "CustomNotificationType", "ExternalCredential",
     "ProductSpecificationType", "EmailTemplate") or (t == "StaticResource" and not n.startswith("SNA_"))),
 ("02-object-config", "Record types, business processes, field sets, validation rules, compact layouts, list views, quick actions, alerts, LWC",
   lambda t, n: t in ("RecordType", "BusinessProcess", "ProductSpecificationRecType", "CompactLayout", "FieldSet",
     "ValidationRule", "ListView", "WorkflowAlert", "QuickAction", "LightningComponentBundle")),
 ("03-flows", "Flows, including the worker flows that batch job definitions call",
   lambda t, n: t == "Flow" and n not in REVIEW_FLOWS and n not in BATCH_LAUNCHER_FLOWS),
 ("04-batch-jobs", "Batch job definitions (each points at a worker flow from 03)",
   lambda t, n: t == "BatchProcessJobDefinition"),
 ("05-batch-launcher-flows", "Flows that start the batch jobs from 04",
   lambda t, n: t == "Flow" and n in BATCH_LAUNCHER_FLOWS),
 ("06-ui", "Page layouts, Lightning pages, tabs",
   lambda t, n: t in ("Layout", "FlexiPage", "CustomTab")),
 ("07-lifesciences-categories", "Life Sciences Cloud config categories",
   lambda t, n: t == "LifeSciConfigCategory"),
 ("08-lifesciences-records", "Life Sciences Cloud config records (need categories from 07)",
   lambda t, n: t == "LifeSciConfigRecord"),
 ("09-roles", "Role hierarchy",
   lambda t, n: t == "Role"),
 ("10-territories", "Territory type, model and territories",
   lambda t, n: t in ("Territory2Type", "Territory2Model", "Territory2")),
 ("11-data-cloud", "Data Cloud: data sources, streams, DLOs/DMOs, mappings, data kits",
   lambda t, n: t.startswith(("DataSource", "DataStream", "DataKit", "DataPackageKit", "DataSrc", "MktDatalake"))
     or (t in ("CustomObject", "CustomField") and DLM(n))),
 ("12-experience-site", "Experience Cloud site LSCAlfasigma",
   lambda t, n: t in ("Network", "CustomSite", "ExperienceBundle", "NavigationMenu")
     or (t == "StaticResource" and n.startswith("SNA_"))),
]
REVIEW = ("99-review-before-prod", "NOT for production as-is: system-generated, demo/test or superseded components",
   lambda t, n, c: SYSTEM_USER in c["users"] and len(c["users"]) == 1 or (t == "Flow" and n in REVIEW_FLOWS) or t == "SiteDotCom")
SECURITY = ("13-security", "Permission sets and profiles, deployed last with the components they grant access to")

buckets = defaultdict(lambda: defaultdict(set))
unassigned = []
for c in comps:
    t, n = c["type"], c["name"]
    if (t, n) in GONE:
        c["stage"] = "REMOVED_FROM_SOURCE_ORG"; continue
    if REVIEW[2](t, n, c):
        stage = REVIEW[0]
    elif t in ("PermissionSet", "Profile"):
        stage = SECURITY[0]
    else:
        stage = next((s for s, _, p in STAGES if p(t, n)), None)
        if stage is None:
            unassigned.append(c); continue
    mtype, member = ("Settings", "ExperienceBundle") if t == "ExperienceBundleSettings" else (t, n)
    buckets[stage][mtype].add(member)
    c["stage"] = stage

# Profiles only carry permissions for components named in the same manifest,
# so 13-security also lists the custom objects, fields, record types, layouts,
# and tabs they reference. Re-deploying those is a no-op.
for t in ("CustomField", "RecordType", "Layout", "CustomTab"):
    for m in buckets["01-schema"].get(t, set()) | buckets["02-object-config"].get(t, set()) | buckets["06-ui"].get(t, set()):
        buckets[SECURITY[0]][t].add(m)
for m in buckets["01-schema"].get("CustomObject", set()):
    if CUSTOM_OBJ(m):
        buckets[SECURITY[0]]["CustomObject"].add(m)

def write(stage, title):
    types = buckets.get(stage)
    if not types: return 0
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             f'<!-- {stage}: {title} -->',
             '<Package xmlns="http://soap.sforce.com/2006/04/metadata">']
    total = 0
    for t in sorted(types):
        lines.append("    <types>")
        for m in sorted(types[t]):
            lines.append(f"        <members>{m}</members>"); total += 1
        lines.append(f"        <name>{t}</name>")
        lines.append("    </types>")
    lines += [f"    <version>{API}</version>", "</Package>", ""]
    open(os.path.join(out_dir, stage + ".xml"), "w").write("\n".join(lines))
    return total

os.makedirs(out_dir, exist_ok=True)
for s, title, _ in STAGES: print(f"{s:30} {write(s, title):5}")
print(f"{SECURITY[0]:30} {write(*SECURITY):5}")
print(f"{REVIEW[0]:30} {write(REVIEW[0], REVIEW[1]):5}")
with open(os.path.join(out_dir, "inventory.csv"), "w", newline="") as f:
    w = csv.writer(f); w.writerow(["stage", "type", "name", "last_deployed_utc", "deployed_by", "deploy_ids"])
    for c in sorted(comps, key=lambda c: (c.get("stage", "zz"), c["type"], c["name"])):
        w.writerow([c.get("stage", "UNASSIGNED"), c["type"], c["name"], c["last"], "; ".join(c["users"]), " ".join(c["deploys"])])
if unassigned:
    print("UNASSIGNED:", sorted({c["type"] for c in unassigned})); sys.exit(1)
