# tests/test_data_store.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def test_store_and_retrieve():
    from data_store import DataStore
    ds = DataStore()
    ds.store("activities", [{"molecule_chembl_id": "CHEMBL25", "pchembl_value": 7.8}])
    assert ds.get("activities") == [{"molecule_chembl_id": "CHEMBL25", "pchembl_value": 7.8}]

def test_get_missing_key_returns_none():
    from data_store import DataStore
    ds = DataStore()
    assert ds.get("nonexistent") is None

def test_snapshot_and_diff_new_key():
    from data_store import DataStore
    ds = DataStore()
    ds.store("activities", [{"a": 1}])
    snap = ds.snapshot()
    ds.store("molecules", [{"b": 2}])
    new_tables = ds.diff_since(snap)
    assert "molecules" in new_tables
    assert "activities" not in new_tables

def test_snapshot_and_diff_updated_value():
    from data_store import DataStore
    ds = DataStore()
    ds.store("activities", [{"a": 1}])
    snap = ds.snapshot()
    ds.store("activities", [{"a": 2}])  # same key, new value
    new_tables = ds.diff_since(snap)
    assert "activities" in new_tables
    assert new_tables["activities"] == [{"a": 2}]

def test_join_tables_inner():
    from data_store import DataStore
    ds = DataStore()
    ds.store("activities", [
        {"molecule_chembl_id": "CHEMBL25", "pchembl_value": 7.8},
        {"molecule_chembl_id": "CHEMBL100", "pchembl_value": 6.0},
    ])
    ds.store("molecules", [
        {"molecule_chembl_id": "CHEMBL25", "canonical_smiles": "CC", "max_phase": 4},
    ])
    result = ds.join("activities", "molecules", on="molecule_chembl_id")
    assert len(result) == 1
    assert result[0]["pchembl_value"] == 7.8
    assert result[0]["canonical_smiles"] == "CC"

def test_filter_table_gte():
    from data_store import DataStore
    ds = DataStore()
    ds.store("activities", [
        {"pchembl_value": 7.8},
        {"pchembl_value": 5.0},
        {"pchembl_value": 6.5},
    ])
    result = ds.filter("activities", column="pchembl_value", operator="gte", value=6.5)
    assert len(result) == 2

def test_sort_table():
    from data_store import DataStore
    ds = DataStore()
    ds.store("activities", [
        {"pchembl_value": 5.0},
        {"pchembl_value": 7.8},
        {"pchembl_value": 6.5},
    ])
    result = ds.sort("activities", column="pchembl_value", ascending=False)
    assert result[0]["pchembl_value"] == 7.8
    assert result[-1]["pchembl_value"] == 5.0
