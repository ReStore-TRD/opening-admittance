import warnings
from typing import Type, List, Optional, Dict

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

def query_option(prompt: str, choices: list[str]) -> str | None:
    print(prompt)
    print("  0) CANCEL")
    for i, name in enumerate(choices, start=1):
        print(f"  {i}) -> \"{name}\"")
   
    sheet_number = -1
    while sheet_number == -1:
        raw_value = input(f"{prompt} [0 - {len(choices)}]: ").strip()
        if raw_value.isdigit():
            if 0 <= (raw_digit := int(raw_value)) <= len(choices):
                sheet_number = raw_digit

    if sheet_number <= 0:
        return None
    else:
        sheet_index = sheet_number - 1
        return choices[sheet_index]

def select_sheet_query(sheets: dict, title: Optional[str] = None) -> str | None:
    sheet_names = [sheet["properties"]["title"] for sheet in sheets]
    return query_option(f"Select {title or 'sheet'}", sheet_names)


def column_binding_query(binding_name: str, target_names: List[str], column_names: List[str]) -> Dict[str, int] | None:
    
    # dictionary from target name to column index
    bindings = {}
    
    for target_field in target_names:
        selected_column = query_option(f"Select columns for {binding_name}:{target_field}", column_names)
        if selected_column is None:
            return None
        bindings[target_field] = column_names.index(selected_column)

    from binding import verify_column_bindings
    if verify_column_bindings(target_names, bindings):
        return bindings
    return None
