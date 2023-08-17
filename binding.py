import json
import os
import tkinter as tk
from typing import List, Dict, Type, Tuple, Optional

from interfaces import open_column_name_binding_window


def bind(headers: List[str], datatype: Type) -> Dict[str, int]:
    # check if {datatype}_bindings.json exists
    binding_path = f"{datatype.__name__.lower()}_bindings.json"
    # Get constructor arguments, excluding self
    datatype_ctor_args = datatype.__init__.__code__.co_varnames[1:datatype.__init__.__code__.co_argcount]
    if os.path.exists(binding_path):
        with open(binding_path, "r") as f:
            column_bindings = json.load(f)
        if verify_column_bindings(datatype_ctor_args, column_bindings):
            return column_bindings

    column_bindings = open_column_name_binding_window(datatype_ctor_args, headers)
    if column_bindings is None:
        return None
    with open(binding_path, "w") as f:
        json.dump(column_bindings, f)

    return column_bindings


def bind_names(headers: List[str], target_names: List[str], binding_filename: Optional[str] = None) -> Dict[str, int]:
    # check if bindings/{datatype}_bindings.json exists
    binding_filename = f"bindings/{binding_filename}"
    if binding_filename:
        if os.path.exists(binding_filename):
            with open(binding_filename, "r") as f:
                column_bindings = json.load(f)
            if verify_column_bindings(target_names, column_bindings):
                return column_bindings

    column_bindings = open_column_name_binding_window(target_names, headers)
    if column_bindings is None:
        return None
    if binding_filename:
        os.makedirs("bindings", exist_ok=True)
        with open(binding_filename, "w") as f:
            json.dump(column_bindings, f)

    return column_bindings


def verify_column_bindings(names: List[str], column_bindings: Dict[str, int]) -> bool:
    return set(names) == set(column_bindings.keys())



