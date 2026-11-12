# Production release manifests (from lscqa)

These manifests list every component deployed to **lscqa** (`oneview-eu--lscqa`) in all
**53 successful, non-validation deployments** between **2026-11-01 and 2026-11-12**.
That is 3,139 distinct components. Every manifest was checked by retrieving it from
lscqa on 2026-11-12, and all of them retrieved with no warnings.

`inventory.csv` lists every component with its stage, last deploy date, who deployed it,
and the deploy IDs. Use it to trace any line back to a deployment.

## Deploy order

Deploy the files strictly in this order. Each stage relies on the ones before it.

| # | File | Items | Why it's at this point |
|---|------|------:|------------------------|
| 00 | `00-org-settings.xml` | 1 | ExperienceBundle setting must be on before the site in 12 can deploy |
| 01 | `01-schema.xml` | 326 | Value sets, custom objects, fields, labels, static resources, notification type, email templates, external credential, product spec types. Everything else references these |
| 02 | `02-object-config.xml` | 101 | Record types, business process, field sets, validation rules, compact layouts, list views, quick actions, email alert, LWC `valVisitScript`. These need the fields from 01 |
| 03 | `03-flows.xml` | 14 | Flows, including the worker flows the batch jobs call |
| 04 | `04-batch-jobs.xml` | 4 | `BatchProcessJobDefinition`s point at worker flows in 03 |
| 05 | `05-batch-launcher-flows.xml` | 3 | Flows that start the batch jobs in 04 |
| 06 | `06-ui.xml` | 120 | Page layouts, Lightning pages, tabs. These reference fields, quick actions, LWC and flows |
| 07 | `07-lifesciences-categories.xml` | 58 | Life Sciences config categories |
| 08 | `08-lifesciences-records.xml` | 209 | Life Sciences config records, which belong to the categories in 07 |
| 09 | `09-roles.xml` | 844 | Role hierarchy. The parent/child order is resolved within the single deploy |
| 10 | `10-territories.xml` | 428 | Territory2Type `VeevaAlign`, Territory2Model `VeevaAlign` and its 426 territories |
| 11 | `11-data-cloud.xml` | 975 | Data Cloud data sources, streams, DLO/DMO objects and fields, mappings, data kits |
| 12 | `12-experience-site.xml` | 5 | Site `LSCAlfasigma`: Network, CustomSite, ExperienceBundle, navigation menu, CDN static resource |
| 13 | `13-security.xml` | 429 | 19 permission sets and 7 profiles, deployed last (see below) |
| 99 | `99-review-before-prod.xml` | 22 | **Not for production as-is**. See "Excluded" |

### Why profiles are deployed last, with extra components

A profile retrieve only includes permissions for components named **in the same
manifest**. So `13-security.xml` also lists the custom objects, fields, record types,
layouts and tabs from 01, 02 and 06. Those are already deployed by then, so deploying
them again changes nothing, but it is what puts field-level security, record type and
layout assignments into the profiles. Permission sets retrieve with all their permissions.

Standard-object CRUD permissions on profiles (for example Account) are **not** included,
because that would need the whole standard object definition in the manifest. Manage
those through the permission sets.

## Prerequisites in production (do these before stage 00)

- **Installed packages at the same or a newer version than lscqa:**
  - Life Sciences Cloud for Customer Engagement (`lsc4ce`) 264.10
  - Salesforce Standard Data Model (`ssot`)
  - CDPAdvertising
  - Sales Insights
- **Features enabled:**
  - Data Cloud provisioned, with the Salesforce Home and VEEVA connections set up
  - Enterprise Territory Management
  - Digital Experiences, with the site domain configured
  - Person Accounts
- **`AL_Run_Account_Summarization_Batch_Job`** calls the managed batch job
  `prvd_sum__SumProviderAcct`, which must exist in production.

## After deployment (manual steps)

- **ExternalCredential `MuleSoft_Provider_Search_EC`:** principals and secrets are never
  deployed. Re-enter them in production.
- **Data Cloud:** after stage 11, open each data kit in Data Cloud Setup and deploy its
  streams and mappings. The kit definitions are named `DataLoad_DEV_QA_*` and
  `DataLoad_INT_QA_*`; consider renaming them for production.
- **Experience site:** publish `LSCAlfasigma` and check the guest user and its sharing.
- **Flows:** `AL_Run_Account_Summarization_Batch_Job` and `Update_Primary_Address` are
  **Draft** in lscqa and deploy inactive. Activate them only if they are meant to run.
- **Profiles:** both `AL Field Sales Rep` and `AL Field Sales Manager` exist. A profile
  called `AL Field Sales Representative` was deployed on 2026-11-03 but no longer exists in
  lscqa (renamed or deleted), so it is excluded. Confirm which name production should use.

## Excluded

- **`99-review-before-prod.xml`** (not deployed by the script):
  - Partner enablement (PRM) reports, report folders, report types and dashboard created
    by *Automated Process*. Salesforce generates these when the feature is enabled, so
    they should not be deployed.
  - Test and demo survey flows: `cb_survey_test_1`, `cb_survey_test_2_mobile`,
    `survey_for_demo_2`, `survey_for_demo_29_10`.
  - `Account_Segment_Update`, which is an **InvalidDraft** in lscqa.
  - SiteDotCom `LSCAlfasigma1`. The site is deployed as an ExperienceBundle in 12, and
    deploying both can conflict.
- **Removed from lscqa after it was deployed** (in `inventory.csv` as
  `REMOVED_FROM_SOURCE_ORG`):
  - Profile `AL Field Sales Representative`
  - DataKitObjectTemplate `STGTransform1`
  - DataPackageKitObject `DataLoad_INT_QA_Package2_1794402693583`

## Not covered by these files

- **Changes older than 2026-11-01.** Salesforce keeps deployment history for about 30
  days, and that is all lscqa still has.
- **Changes made by hand in lscqa Setup** rather than deployed. Check Setup → View Setup
  Audit Trail for anything that should also go to production.
- **Deletions.** No deployment in this window deleted anything, so no
  `destructiveChanges.xml` is needed.

## How to deploy

```bash
# Rehearse the full sequence in a UAT/full-copy sandbox first, then production:
sf org login web --instance-url https://<prod-my-domain>.my.salesforce.com --alias prod
scripts/deploy_release.sh lscqa prod             # validate + deploy each stage in order
scripts/deploy_release.sh lscqa prod --from 06   # resume from a stage after fixing a failure
```

The script retrieves each stage from lscqa, validates it against the target with a dry
run, and only then deploys it, stopping at the first failure. No `--test-level` is passed,
so production runs local tests only when a stage contains Apex (none do today).

Before a release, check that nothing new has reached lscqa since this list was built.
To rebuild the list:

```bash
scripts/export_deploy_history.sh lscqa /tmp/lscqa-history
scripts/build_release_manifests.py /tmp/lscqa-history/components.json manifest/prod-release
```
