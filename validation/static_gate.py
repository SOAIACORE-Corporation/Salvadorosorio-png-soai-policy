from pathlib import Path
import json, re, hashlib
from jsonschema import Draft202012Validator

root = Path(__file__).resolve().parents[1]
errors=[]
checks=[]
def check(name, cond, detail=''):
    checks.append({'name':name,'pass':bool(cond),'detail':detail})
    if not cond: errors.append(name)

# Schemas
for p in sorted((root/'schemas').glob('*.json')):
    try:
        Draft202012Validator.check_schema(json.loads(p.read_text(encoding='utf-8')))
        check('schema:'+p.name, True)
    except Exception as e:
        check('schema:'+p.name, False, str(e))

sql='\n'.join(p.read_text(encoding='utf-8') for p in sorted((root/'db/migrations').glob('*.sql')))
required_schemas=['soa_core','soa_identity','soa_evidence','soa_intelligence','soa_adjudication','soa_ops','experimental']
for s in required_schemas:
    check('namespace:'+s, f'CREATE SCHEMA IF NOT EXISTS {s}' in sql)

required_tables=[
'projects','corpora','contexts','context_capsules','relationships','claims','claim_relations','claim_evidence','context_graph_edges',
'observed_actors','canonical_subjects','aliases','identity_claims','identity_decisions',
'source_artifacts','evidence_objects','evidence_transforms','evidence_references',
'analysis_profiles','authorization_decisions','calibration_registry','external_source_registry','runs','model_runs','tool_runs','embeddings',
'adjudications','adjudication_ratings','ground_truth_ledgers','ground_truth_items','jobs','context_receipts','deployment_receipts','schema_registry'
]
for t in required_tables:
    check('table:'+t, bool(re.search(r'CREATE TABLE(?: IF NOT EXISTS)?\s+[a-z_]+\.'+re.escape(t)+r'\b',sql,re.I)))

check('pgvector-extension','CREATE EXTENSION IF NOT EXISTS vector' in sql)
check('probability-guard','probability_estimate IS NULL' in sql and 'calibration_ref IS NOT NULL' in sql)
check('contextgraph-postgres','CREATE TABLE soa_core.context_graph_edges' in sql)
check('model-modes', all(x in sql for x in ["'MOCK'","'REPLAY'","'LIVE'"]))
check('no-cloud-vendor-in-ddl', not re.search(r'\b(AZURE|GCP|CLOUD RUN|CONTAINER APPS)\b',sql,re.I))
check('no-destructive-ddl', not re.search(r'\bDROP\s+(TABLE|SCHEMA|DATABASE)\b',sql,re.I))
check('identity-never-merge', "'NEVER_MERGE'" in sql)
check('evidence-admissible', "'ADMISSIBLE'" in sql and "'VERIFIED'" in sql)
check('conditional-human-review', "CHECK (human_review_mode IN ('NONE','OPTIONAL','REQUIRED'))" in sql)

pdoc=(root/'docs/persistence/SOAIACORE_CANONICAL_PERSISTENCE_MODEL_v1.0.md').read_text(encoding='utf-8')
check('maturity-M0-M3', all(x in pdoc for x in ['M0 EXPERIMENTAL','M1 CANDIDATE','M2 CANONICAL','M3 PRODUCTION_FROZEN']) or all(x in pdoc for x in ['M0 EXPERIMENTAL','M1 CANDIDATE','M2 CANONICAL','M3 PRODUCTION-FROZEN']))
check('epistemic-reservation','E0-E5' in pdoc)
check('local-first','Day-to-day: local PostgreSQL + pgvector.' in pdoc)

result={'status':'PASS' if not errors else 'FAIL','checks':checks,'errors':errors}
out=root/'validation/STATIC_AND_SEMANTIC_GATE.json'
out.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({'status':result['status'],'passed':sum(c['pass'] for c in checks),'total':len(checks),'errors':errors},indent=2))
raise SystemExit(1 if errors else 0)
