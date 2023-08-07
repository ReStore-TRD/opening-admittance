import json
import os
import tkinter as tk
from typing import List, Dict, Type, Tuple, Optional

from interfaces import open_column_name_binding_window


def bind(headers: List[str], datatype: Type) -> Dict[str, int]:
    # check if {datatype}_bindings.json exists
    binding_path = f"{datatype.__name__.lower()}_bindings.json"
    if os.path.exists(binding_path):
        with open(binding_path, "r") as f:
            column_bindings = json.load(f)
            if verify_column_bindings(datatype, column_bindings):
                return column_bindings

    column_bindings = open_column_name_binding_window(datatype, headers)
    if column_bindings is None:
        return None
    with open(binding_path, "w") as f:
        json.dump(column_bindings, f)

    return column_bindings


def verify_column_bindings(datatype: Type, column_bindings: Dict[str, int]) -> bool:
    # Get constructor arguments, excluding self
    args = datatype.__init__.__code__.co_varnames[1:]
    return set(args) == set(column_bindings.keys())





