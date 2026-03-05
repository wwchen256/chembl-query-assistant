import logging
from chembl_webresource_client.new_client import new_client
from chembl_webresource_client.settings import Settings

from config import CHEMBL_TIMEOUT, MAX_RESULTS, DEFAULT_RESULTS_LIMIT

logger = logging.getLogger(__name__)

Settings.Instance().TIMEOUT = CHEMBL_TIMEOUT


def _clamp_limit(limit):
    if limit is None:
        return DEFAULT_RESULTS_LIMIT
    return max(1, min(int(limit), MAX_RESULTS))


def _safe_get(obj, key, default="N/A"):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return default


def _extract_molecule_fields(mol):
    props = _safe_get(mol, "molecule_properties", {}) or {}
    structs = _safe_get(mol, "molecule_structures", {}) or {}
    return {
        "molecule_chembl_id": _safe_get(mol, "molecule_chembl_id"),
        "pref_name": _safe_get(mol, "pref_name"),
        "molecule_type": _safe_get(mol, "molecule_type"),
        "max_phase": _safe_get(mol, "max_phase"),
        "molecular_weight": _safe_get(props, "mw_freebase"),
        "alogp": _safe_get(props, "alogp"),
        "hba": _safe_get(props, "hba"),
        "hbd": _safe_get(props, "hbd"),
        "psa": _safe_get(props, "psa"),
        "ro5_violations": _safe_get(props, "num_ro5_violations"),
        "canonical_smiles": _safe_get(structs, "canonical_smiles"),
    }


def search_molecules(
    name=None,
    max_molecular_weight=None,
    min_molecular_weight=None,
    max_logp=None,
    max_phase=None,
    ro5_violations=None,
    limit=None,
):
    limit = _clamp_limit(limit)
    molecule = new_client.molecule

    filters = {}
    if name:
        filters["pref_name__icontains"] = name
    if max_molecular_weight is not None:
        filters["molecule_properties__mw_freebase__lte"] = max_molecular_weight
    if min_molecular_weight is not None:
        filters["molecule_properties__mw_freebase__gte"] = min_molecular_weight
    if max_logp is not None:
        filters["molecule_properties__alogp__lte"] = max_logp
    if max_phase is not None:
        filters["max_phase"] = max_phase
    if ro5_violations is not None:
        filters["molecule_properties__num_ro5_violations"] = ro5_violations

    logger.info(f"search_molecules filters={filters} limit={limit}")
    queryset = molecule.filter(**filters) if filters else molecule.all()
    results = list(queryset[:limit])
    return [_extract_molecule_fields(m) for m in results]


def get_molecule_by_id(chembl_id):
    logger.info(f"get_molecule_by_id chembl_id={chembl_id}")
    molecule = new_client.molecule
    mol = molecule.get(chembl_id)
    if mol is None:
        return []
    return [_extract_molecule_fields(mol)]


def search_targets(
    name=None,
    gene_name=None,
    organism=None,
    target_type=None,
    uniprot_id=None,
    limit=None,
):
    limit = _clamp_limit(limit)
    target = new_client.target

    filters = {}
    if name:
        filters["pref_name__icontains"] = name
    if organism:
        filters["organism__icontains"] = organism
    if target_type:
        filters["target_type__iexact"] = target_type
    if uniprot_id:
        filters["target_components__accession"] = uniprot_id

    logger.info(f"search_targets filters={filters} limit={limit}")

    if gene_name and not filters:
        queryset = target.search(gene_name)
    elif gene_name:
        queryset = target.filter(**filters)
    else:
        queryset = target.filter(**filters) if filters else target.all()

    results = list(queryset[:limit])

    out = []
    for t in results:
        components = _safe_get(t, "target_components", []) or []
        accessions = []
        for comp in components:
            acc = _safe_get(comp, "accession")
            if acc and acc != "N/A":
                accessions.append(acc)
        out.append({
            "target_chembl_id": _safe_get(t, "target_chembl_id"),
            "pref_name": _safe_get(t, "pref_name"),
            "target_type": _safe_get(t, "target_type"),
            "organism": _safe_get(t, "organism"),
            "accessions": ", ".join(accessions) if accessions else "N/A",
        })
    return out


def get_activities(
    target_chembl_id=None,
    molecule_chembl_id=None,
    target_uniprot_id=None,
    standard_type=None,
    pchembl_value_min=None,
    assay_type=None,
    limit=None,
):
    limit = _clamp_limit(limit)
    activity = new_client.activity

    # Resolve UniProt accession to ChEMBL target ID if needed
    if target_uniprot_id and not target_chembl_id:
        target = new_client.target
        t_results = list(target.filter(target_components__accession=target_uniprot_id)[:1])
        if t_results:
            target_chembl_id = t_results[0].get("target_chembl_id")
        else:
            return [{"error": f"No ChEMBL target found for UniProt {target_uniprot_id}"}]

    filters = {}
    if target_chembl_id:
        filters["target_chembl_id"] = target_chembl_id
    if molecule_chembl_id:
        filters["molecule_chembl_id"] = molecule_chembl_id
    if standard_type:
        filters["standard_type__iexact"] = standard_type
    if pchembl_value_min is not None:
        filters["pchembl_value__gte"] = pchembl_value_min
    if assay_type:
        filters["assay_type"] = assay_type

    if not filters:
        return [{"error": "At least one of target_chembl_id or molecule_chembl_id is required"}]

    logger.info(f"get_activities filters={filters} limit={limit}")
    results = list(activity.filter(**filters)[:limit])

    return [
        {
            "molecule_chembl_id": _safe_get(a, "molecule_chembl_id"),
            "molecule_pref_name": _safe_get(a, "molecule_pref_name"),
            "target_chembl_id": _safe_get(a, "target_chembl_id"),
            "target_pref_name": _safe_get(a, "target_pref_name"),
            "standard_type": _safe_get(a, "standard_type"),
            "standard_value": _safe_get(a, "standard_value"),
            "standard_units": _safe_get(a, "standard_units"),
            "pchembl_value": _safe_get(a, "pchembl_value"),
            "assay_chembl_id": _safe_get(a, "assay_chembl_id"),
            "assay_type": _safe_get(a, "assay_type"),
        }
        for a in results
    ]


def get_approved_drugs(
    usan_stem=None,
    min_approval_year=None,
    max_approval_year=None,
    indication=None,
    limit=None,
):
    limit = _clamp_limit(limit)
    logger.info(
        f"get_approved_drugs usan_stem={usan_stem} years={min_approval_year}-{max_approval_year} "
        f"indication={indication} limit={limit}"
    )

    if indication:
        drug_ind = new_client.drug_indication
        ind_results = list(drug_ind.filter(efo_term__icontains=indication)[:limit])
        out = []
        seen = set()
        for di in ind_results:
            mol_id = _safe_get(di, "molecule_chembl_id")
            if mol_id in seen or mol_id == "N/A":
                continue
            seen.add(mol_id)
            out.append({
                "molecule_chembl_id": mol_id,
                "pref_name": _safe_get(di, "pref_name", _safe_get(di, "molecule_chembl_id")),
                "indication": _safe_get(di, "efo_term"),
                "max_phase_for_ind": _safe_get(di, "max_phase_for_ind"),
            })
        return out

    molecule = new_client.molecule
    filters = {"max_phase": 4}
    if min_approval_year is not None:
        filters["first_approval__gte"] = min_approval_year
    if max_approval_year is not None:
        filters["first_approval__lte"] = max_approval_year
    if usan_stem:
        filters["usan_stem__icontains"] = usan_stem

    results = list(molecule.filter(**filters)[:limit])
    return [
        {
            "molecule_chembl_id": _safe_get(m, "molecule_chembl_id"),
            "pref_name": _safe_get(m, "pref_name"),
            "first_approval": _safe_get(m, "first_approval"),
            "usan_stem": _safe_get(m, "usan_stem"),
            "max_phase": _safe_get(m, "max_phase"),
        }
        for m in results
    ]


def similarity_search(
    smiles=None,
    chembl_id=None,
    similarity_threshold=70,
    limit=None,
):
    limit = _clamp_limit(limit)
    similarity = new_client.similarity

    if smiles:
        logger.info(f"similarity_search smiles={smiles[:50]}... threshold={similarity_threshold}")
        queryset = similarity.filter(smiles=smiles, similarity=similarity_threshold)
    elif chembl_id:
        logger.info(f"similarity_search chembl_id={chembl_id} threshold={similarity_threshold}")
        queryset = similarity.filter(chembl_id=chembl_id, similarity=similarity_threshold)
    else:
        return [{"error": "Either smiles or chembl_id is required"}]

    results = list(queryset[:limit])
    return [
        {
            "molecule_chembl_id": _safe_get(m, "molecule_chembl_id"),
            "pref_name": _safe_get(m, "pref_name"),
            "similarity": _safe_get(m, "similarity"),
            "molecular_weight": _safe_get(
                _safe_get(m, "molecule_properties", {}) or {}, "mw_freebase"
            ),
            "canonical_smiles": _safe_get(
                _safe_get(m, "molecule_structures", {}) or {}, "canonical_smiles"
            ),
        }
        for m in results
    ]


def substructure_search(smiles=None, chembl_id=None, limit=None):
    limit = _clamp_limit(limit)
    substructure = new_client.substructure

    if smiles:
        logger.info(f"substructure_search smiles={smiles[:50]}...")
        queryset = substructure.filter(smiles=smiles)
    elif chembl_id:
        logger.info(f"substructure_search chembl_id={chembl_id}")
        queryset = substructure.filter(chembl_id=chembl_id)
    else:
        return [{"error": "Either smiles or chembl_id is required"}]

    results = list(queryset[:limit])
    return [_extract_molecule_fields(m) for m in results]
