import logging
import re

import requests
from chembl_webresource_client.new_client import new_client

from config import MAX_RESULTS, DEFAULT_RESULTS_LIMIT

logger = logging.getLogger(__name__)

OT_GRAPHQL_URL = "https://api.platform.opentargets.org/api/v4/graphql"
UNIPROT_SEARCH_URL = "https://rest.uniprot.org/uniprotkb/search"
REQUEST_TIMEOUT = 15

# Patterns for detecting input type
_CHEMBL_RE = re.compile(r"^CHEMBL\d+$", re.IGNORECASE)
_UNIPROT_RE = re.compile(
    r"^[OPQ][0-9][A-Z0-9]{3}[0-9]$|^[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2}$"
)


def _clamp_limit(limit):
    if limit is None:
        return DEFAULT_RESULTS_LIMIT
    return max(1, min(int(limit), MAX_RESULTS))


# ---------------------------------------------------------------------------
# OpenTargets GraphQL helpers
# ---------------------------------------------------------------------------

def _ot_graphql(query, variables):
    """Execute a GraphQL query against the OpenTargets Platform API."""
    resp = requests.post(
        OT_GRAPHQL_URL,
        json={"query": query, "variables": variables},
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        logger.warning(f"OpenTargets GraphQL errors: {data['errors']}")
    return data.get("data")


def _ot_map_ids(query):
    """Map a free-text query to an Ensembl gene ID via OpenTargets mapIds."""
    gql = """
    query mapIds($terms: [String!]!, $entities: [String!]!) {
      mapIds(queryTerms: $terms, entityNames: $entities) {
        mappings {
          hits {
            id
          }
        }
      }
    }
    """
    data = _ot_graphql(gql, {"terms": [query], "entities": ["target"]})
    if not data or not data.get("mapIds"):
        return None

    mappings = data["mapIds"].get("mappings") or []
    for mapping in mappings:
        hits = mapping.get("hits") or []
        if hits:
            return hits[0].get("id")

    return None


def _ot_target_details(ensembl_id):
    """Get target details from OpenTargets by Ensembl ID."""
    gql = """
    query target($id: String!) {
      target(ensemblId: $id) {
        id
        approvedSymbol
        approvedName
        proteinIds {
          id
          source
        }
        synonyms {
          label
        }
      }
    }
    """
    data = _ot_graphql(gql, {"id": ensembl_id})
    if not data or not data.get("target"):
        return None

    t = data["target"]
    protein_ids = t.get("proteinIds") or []
    uniprot_id = None
    for p in protein_ids:
        if p.get("source") == "uniprot_swissprot":
            uniprot_id = p.get("id")
            break
    if not uniprot_id and protein_ids:
        uniprot_id = protein_ids[0].get("id")

    synonyms_raw = t.get("synonyms") or []
    synonyms = [s.get("label", "") for s in synonyms_raw if s.get("label")]

    return {
        "ensembl_id": t.get("id"),
        "approved_symbol": t.get("approvedSymbol"),
        "approved_name": t.get("approvedName"),
        "uniprot_id": uniprot_id,
        "synonyms": synonyms,
    }


# ---------------------------------------------------------------------------
# UniProt helpers
# ---------------------------------------------------------------------------

def _uniprot_search(query):
    """Search UniProt for a gene symbol/name, restricted to human (taxon 9606).

    Tries gene name search first, then falls back to protein name search
    for casual names like 'p38 alpha'.
    """
    # Try gene name search first (works for EGFR, MAPK14, etc.)
    resp = requests.get(
        UNIPROT_SEARCH_URL,
        params={
            "query": f"((gene:{query}) AND (taxonomy_id:9606))",
            "fields": "accession,gene_names,protein_name,organism_name",
            "format": "json",
            "size": 5,
        },
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])

    # Fallback: protein name search for casual names (p38 alpha, etc.)
    if not results:
        resp = requests.get(
            UNIPROT_SEARCH_URL,
            params={
                "query": f'((protein_name:"{query}") AND (taxonomy_id:9606))',
                "fields": "accession,gene_names,protein_name,organism_name",
                "format": "json",
                "size": 5,
            },
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])

    if not results:
        return None

    entry = results[0]
    accession = entry.get("primaryAccession")
    genes = entry.get("genes", [])
    gene_names = []
    for g in genes:
        gn = g.get("geneName", {}).get("value")
        if gn:
            gene_names.append(gn)
        for syn in g.get("synonyms", []):
            v = syn.get("value")
            if v:
                gene_names.append(v)

    protein_name = ""
    pn = entry.get("proteinDescription", {}).get("recommendedName")
    if pn:
        protein_name = pn.get("fullName", {}).get("value", "")

    return {
        "accession": accession,
        "gene_names": gene_names,
        "protein_name": protein_name,
    }


# ---------------------------------------------------------------------------
# ChEMBL target lookup by UniProt
# ---------------------------------------------------------------------------

def _chembl_targets_by_uniprot(accession):
    """Find ChEMBL target IDs for a UniProt accession."""
    target = new_client.target
    results = list(target.filter(target_components__accession=accession)[:10])
    return [r.get("target_chembl_id") for r in results if r.get("target_chembl_id")]


# ---------------------------------------------------------------------------
# Public functions (one per tool)
# ---------------------------------------------------------------------------

def resolve_target(query):
    """Resolve any target identifier to a normalized record.

    Accepts gene symbols (EGFR), casual names (p38 alpha),
    UniProt accessions (P00533), or ChEMBL IDs (CHEMBL203).
    """
    query = query.strip()
    logger.info(f"resolve_target query={query}")

    result = {
        "query": query,
        "gene_symbol": "N/A",
        "approved_name": "N/A",
        "ensembl_id": "N/A",
        "uniprot_id": "N/A",
        "chembl_target_ids": "N/A",
        "common_names": "N/A",
        "source": "N/A",
    }

    try:
        # --- Path 1: ChEMBL ID input ---
        if _CHEMBL_RE.match(query):
            chembl_id = query.upper()
            targets = list(new_client.target.filter(target_chembl_id=chembl_id)[:1])
            if not targets:
                return [{"query": query, "error": f"No target found for {chembl_id}"}]

            t = targets[0]
            components = t.get("target_components", []) or []
            accessions = []
            for comp in components:
                acc = comp.get("accession")
                if acc:
                    accessions.append(acc)

            result["chembl_target_ids"] = chembl_id
            result["source"] = "chembl"

            # Try to enrich via UniProt → OpenTargets
            if accessions:
                result["uniprot_id"] = accessions[0]
                up = _uniprot_search(accessions[0])
                if up and up.get("gene_names"):
                    result["gene_symbol"] = up["gene_names"][0]
                    result["approved_name"] = up.get("protein_name", "N/A")

                    # Try OT for Ensembl ID
                    ot_id = _ot_map_ids(up["gene_names"][0])
                    if ot_id:
                        result["ensembl_id"] = ot_id
                        details = _ot_target_details(ot_id)
                        if details and details.get("synonyms"):
                            result["common_names"] = ", ".join(details["synonyms"][:10])

            return [result]

        # --- Path 2: UniProt accession input ---
        if _UNIPROT_RE.match(query):
            accession = query.upper()
            result["uniprot_id"] = accession
            result["source"] = "uniprot"

            up = _uniprot_search(accession)
            if up:
                result["gene_symbol"] = up["gene_names"][0] if up.get("gene_names") else "N/A"
                result["approved_name"] = up.get("protein_name", "N/A")

            gene = result["gene_symbol"]
            if gene != "N/A":
                ot_id = _ot_map_ids(gene)
                if ot_id:
                    result["ensembl_id"] = ot_id
                    details = _ot_target_details(ot_id)
                    if details and details.get("synonyms"):
                        result["common_names"] = ", ".join(details["synonyms"][:10])

            chembl_ids = _chembl_targets_by_uniprot(accession)
            if chembl_ids:
                result["chembl_target_ids"] = ", ".join(chembl_ids)

            return [result]

        # --- Path 3: Gene symbol or free-text (primary path) ---
        # Try OpenTargets mapIds first
        ensembl_id = _ot_map_ids(query)
        if ensembl_id:
            details = _ot_target_details(ensembl_id)
            if details:
                result["ensembl_id"] = ensembl_id
                result["gene_symbol"] = details.get("approved_symbol", "N/A")
                result["approved_name"] = details.get("approved_name", "N/A")
                result["uniprot_id"] = details.get("uniprot_id", "N/A")
                result["source"] = "opentargets"

                if details.get("synonyms"):
                    result["common_names"] = ", ".join(details["synonyms"][:10])

                # Get ChEMBL target IDs via UniProt accession
                if result["uniprot_id"] != "N/A":
                    chembl_ids = _chembl_targets_by_uniprot(result["uniprot_id"])
                    if chembl_ids:
                        result["chembl_target_ids"] = ", ".join(chembl_ids)

                return [result]

        # Fallback: UniProt search
        up = _uniprot_search(query)
        if up and up.get("accession"):
            result["uniprot_id"] = up["accession"]
            result["gene_symbol"] = up["gene_names"][0] if up.get("gene_names") else "N/A"
            result["approved_name"] = up.get("protein_name", "N/A")
            result["source"] = "uniprot"

            # Try OT again with the resolved gene symbol
            gene = result["gene_symbol"]
            if gene != "N/A":
                ot_id = _ot_map_ids(gene)
                if ot_id:
                    result["ensembl_id"] = ot_id
                    details = _ot_target_details(ot_id)
                    if details and details.get("synonyms"):
                        result["common_names"] = ", ".join(details["synonyms"][:10])

            chembl_ids = _chembl_targets_by_uniprot(up["accession"])
            if chembl_ids:
                result["chembl_target_ids"] = ", ".join(chembl_ids)

            return [result]

        # Nothing found
        return [{"query": query, "error": "Could not resolve target. Try a different name, gene symbol, or ID."}]

    except requests.RequestException as e:
        logger.error(f"resolve_target API error: {e}")
        return [{"query": query, "error": f"API error during resolution: {e}"}]
    except Exception as e:
        logger.error(f"resolve_target unexpected error: {e}")
        return [{"query": query, "error": f"Error resolving target: {e}"}]


def get_drugs_for_target(ensembl_id, limit=None):
    """Get drugs targeting a gene via OpenTargets knownDrugs."""
    limit = _clamp_limit(limit)
    logger.info(f"get_drugs_for_target ensembl_id={ensembl_id} limit={limit}")

    gql = """
    query drugs($id: String!, $size: Int!) {
      target(ensemblId: $id) {
        approvedSymbol
        knownDrugs(size: $size) {
          rows {
            drugId
            prefName
            drugType
            mechanismOfAction
            phase
            status
            disease {
              name
            }
          }
        }
      }
    }
    """
    try:
        data = _ot_graphql(gql, {"id": ensembl_id, "size": limit})
        if not data or not data.get("target"):
            return [{"error": f"No target found for Ensembl ID {ensembl_id}"}]

        target = data["target"]
        known = target.get("knownDrugs") or {}
        rows = known.get("rows") or []

        if not rows:
            symbol = target.get("approvedSymbol", ensembl_id)
            return [{"error": f"No known drugs found for {symbol}"}]

        return [
            {
                "drug_chembl_id": r.get("drugId", "N/A"),
                "drug_name": r.get("prefName", "N/A"),
                "drug_type": r.get("drugType", "N/A"),
                "mechanism_of_action": r.get("mechanismOfAction", "N/A"),
                "phase": r.get("phase", "N/A"),
                "status": r.get("status", "N/A"),
                "disease": (r.get("disease") or {}).get("name", "N/A"),
            }
            for r in rows
        ]

    except requests.RequestException as e:
        logger.error(f"get_drugs_for_target API error: {e}")
        return [{"error": f"OpenTargets API error: {e}"}]


def get_disease_associations(ensembl_id, limit=None):
    """Get diseases associated with a target via OpenTargets."""
    limit = _clamp_limit(limit)
    logger.info(f"get_disease_associations ensembl_id={ensembl_id} limit={limit}")

    gql = """
    query diseases($id: String!, $size: Int!) {
      target(ensemblId: $id) {
        approvedSymbol
        associatedDiseases(page: {size: $size, index: 0}) {
          rows {
            disease {
              id
              name
            }
            score
          }
        }
      }
    }
    """
    try:
        data = _ot_graphql(gql, {"id": ensembl_id, "size": limit})
        if not data or not data.get("target"):
            return [{"error": f"No target found for Ensembl ID {ensembl_id}"}]

        target = data["target"]
        assoc = target.get("associatedDiseases") or {}
        rows = assoc.get("rows") or []

        if not rows:
            symbol = target.get("approvedSymbol", ensembl_id)
            return [{"error": f"No disease associations found for {symbol}"}]

        return [
            {
                "disease_id": (r.get("disease") or {}).get("id", "N/A"),
                "disease_name": (r.get("disease") or {}).get("name", "N/A"),
                "association_score": round(r.get("score", 0), 4),
            }
            for r in rows
        ]

    except requests.RequestException as e:
        logger.error(f"get_disease_associations API error: {e}")
        return [{"error": f"OpenTargets API error: {e}"}]
