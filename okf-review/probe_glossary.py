#!/usr/bin/env python3
"""Probe: is a Dataplex glossary term discoverable by an MCP agent?

v7 Follow-up 7 found the business-glossary `definition` EntryLink is the ONE
KC-native artifact the BQ CA API consumes. This asks a different question for a
different consumer: can an MCP/ADK agent — the Phase 8 Arm D path — see a
glossary term at all, and can it see the `definition` link that gives the term
its meaning?

Creates `okf-metric-probe` / term `avg-monthly-balance` in royston-dev-8253 (us)
and attaches it to `balance_snapshots.balance`. Reversible: --teardown.
"""
import sys, time
from google.api_core import exceptions
from google.cloud import dataplex_v1 as dp

BQ_PROJECT="royston-dev-8253"; PROJECT_NUMBER="404799090046"
DATAPLEX_TYPES_NUM="655216118709"; LOCATION="us"
DATASET="cymbal_bank_v6z_scaffold_demo_copy"; TABLE="balance_snapshots"; COLUMN="balance"
GLOSSARY_ID="okf-metric-probe"; TERM_ID="avg-monthly-balance"
DEFINITION_LINK_TYPE=f"projects/{DATAPLEX_TYPES_NUM}/locations/global/entryLinkTypes/definition"
# One term, many columns: the probe attaches the SAME term to two tables, which
# is the property a column description structurally cannot have.
ATTACHMENTS=[("balance_snapshots","balance"),("accounts","balance")]
def link_id(tbl,col): return f"kcglossary-{tbl}-{col}-{TERM_ID}".replace("_","-").lower()
LINK_ID=link_id(TABLE,COLUMN)
_ref=dp.EntryLink.EntryReference

def entry_name():
    return (f"projects/{PROJECT_NUMBER}/locations/{LOCATION}/entryGroups/@bigquery/entries/"
            f"bigquery.googleapis.com/projects/{BQ_PROJECT}/datasets/{DATASET}/tables/{TABLE}")
def term_entry_name():
    res=f"projects/{PROJECT_NUMBER}/locations/{LOCATION}/glossaries/{GLOSSARY_ID}/terms/{TERM_ID}"
    return f"projects/{PROJECT_NUMBER}/locations/{LOCATION}/entryGroups/@dataplex/entries/{res}"

def setup():
    bg=dp.BusinessGlossaryServiceClient(); cc=dp.CatalogServiceClient()
    gname=bg.glossary_path(BQ_PROJECT,LOCATION,GLOSSARY_ID)
    try: bg.get_glossary(name=gname); print("glossary exists")
    except exceptions.NotFound:
        bg.create_glossary(parent=f"projects/{BQ_PROJECT}/locations/{LOCATION}",
            glossary=dp.Glossary(display_name="OKF metric probe"), glossary_id=GLOSSARY_ID).result(timeout=180)
        print("created glossary")
    tname=bg.glossary_term_path(BQ_PROJECT,LOCATION,GLOSSARY_ID,TERM_ID)
    desc=("Average end-of-month account balance. AVG over balance_snapshots.balance, "
          "which is semi-additive: average it across months, never SUM it.")
    term=dp.GlossaryTerm(name=tname, display_name="Average Monthly Balance", description=desc, parent=gname)
    try:
        bg.get_glossary_term(name=tname); print("term exists")
    except exceptions.NotFound:
        bg.create_glossary_term(parent=gname, term=term, term_id=TERM_ID); print("created term")
    el=dp.EntryLink(entry_link_type=DEFINITION_LINK_TYPE, entry_references=[
        _ref(name=entry_name(), path=f"Schema.{COLUMN}", type_=_ref.Type.SOURCE),
        _ref(name=term_entry_name(), type_=_ref.Type.TARGET)])
    parent=f"projects/{PROJECT_NUMBER}/locations/{LOCATION}/entryGroups/@bigquery"
    for attempt,delay in enumerate([2,3,5,5,10,15,20,20,30,30]):
        try:
            cc.create_entry_link(parent=parent, entry_link=el, entry_link_id=LINK_ID)
            print("created definition link"); return
        except exceptions.AlreadyExists: print("definition link exists"); return
        except exceptions.NotFound:
            if attempt==9: raise
            time.sleep(delay)

def teardown():
    bg=dp.BusinessGlossaryServiceClient(); cc=dp.CatalogServiceClient()
    parent=f"projects/{PROJECT_NUMBER}/locations/{LOCATION}/entryGroups/@bigquery"
    for tbl,col in ATTACHMENTS:
        try: cc.delete_entry_link(name=f"{parent}/entryLinks/{link_id(tbl,col)}"); print("deleted link",tbl,col)
        except exceptions.NotFound: print("link absent",tbl,col)
    for fn,arg,label in [(bg.delete_glossary_term,bg.glossary_term_path(BQ_PROJECT,LOCATION,GLOSSARY_ID,TERM_ID),"term")]:
        try: fn(name=arg); print("deleted",label)
        except exceptions.NotFound: print(label,"absent")
    try:
        bg.delete_glossary(name=bg.glossary_path(BQ_PROJECT,LOCATION,GLOSSARY_ID)).result(timeout=180)
        print("deleted glossary")
    except exceptions.NotFound: print("glossary absent")

if __name__=="__main__":
    teardown() if "--teardown" in sys.argv else setup()
