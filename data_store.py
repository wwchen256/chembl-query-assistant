import pandas as pd

OPERATORS = {
    "eq": lambda col, val: col == val,
    "gt": lambda col, val: col > val,
    "gte": lambda col, val: col >= val,
    "lt": lambda col, val: col < val,
    "lte": lambda col, val: col <= val,
    "contains": lambda col, val: col.astype(str).str.contains(str(val), case=False, na=False),
}


class DataStore:
    def __init__(self, initial=None):
        self._store = dict(initial or {})
        self._versions = {}  # key -> monotonic write counter
        self._counter = 0

    def store(self, name, records):
        self._counter += 1
        self._store[name] = records
        self._versions[name] = self._counter

    def get(self, name):
        return self._store.get(name)

    def keys(self):
        return list(self._store.keys())

    def snapshot(self):
        """Return a copy of current version counters for all keys."""
        return dict(self._versions)

    def diff_since(self, snapshot):
        """Return dict of tables added or updated since snapshot.

        Works for both new keys (not in snapshot) and updated values
        (version counter higher than snapshot's recorded version).
        """
        result = {}
        for k, version in self._versions.items():
            if snapshot.get(k, -1) < version:
                result[k] = self._store[k]
        return result

    def join(self, left, right, on, how="inner"):
        left_data = self._store.get(left)
        right_data = self._store.get(right)
        if left_data is None:
            return [{"error": f"Table '{left}' not found in store. Available: {self.keys()}"}]
        if right_data is None:
            return [{"error": f"Table '{right}' not found in store. Available: {self.keys()}"}]
        df_left = pd.DataFrame(left_data)
        df_right = pd.DataFrame(right_data)
        if on not in df_left.columns:
            return [{"error": f"Column '{on}' not found in '{left}'. Columns: {list(df_left.columns)}"}]
        if on not in df_right.columns:
            return [{"error": f"Column '{on}' not found in '{right}'. Columns: {list(df_right.columns)}"}]
        merged = df_left.merge(df_right, on=on, how=how, suffixes=("", f"_{right}"))
        return merged.to_dict(orient="records")

    def filter(self, table, column, operator, value):
        data = self._store.get(table)
        if data is None:
            return [{"error": f"Table '{table}' not found. Available: {self.keys()}"}]
        op_fn = OPERATORS.get(operator)
        if op_fn is None:
            return [{"error": f"Unknown operator '{operator}'. Use: {list(OPERATORS.keys())}"}]
        df = pd.DataFrame(data)
        if column not in df.columns:
            return [{"error": f"Column '{column}' not found. Columns: {list(df.columns)}"}]
        mask = op_fn(df[column], value)
        return df[mask].to_dict(orient="records")

    def sort(self, table, column, ascending=True):
        data = self._store.get(table)
        if data is None:
            return [{"error": f"Table '{table}' not found. Available: {self.keys()}"}]
        df = pd.DataFrame(data)
        if column not in df.columns:
            return [{"error": f"Column '{column}' not found. Columns: {list(df.columns)}"}]
        return df.sort_values(column, ascending=ascending).to_dict(orient="records")
