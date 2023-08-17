from typing import Union, Type, List, Dict

from googleapiclient.discovery import build

from binding import bind_names, bind
from interfaces import open_select_sheet_dialog_window
from util import get_credentials

class SpreadsheetReader:
    raw_sheets: Dict
    spreadsheet_id: str

    def __init__(self, spreadsheet_id: str, scopes: List[str]):
        self.spreadsheet_id = spreadsheet_id
        self.api = build('sheets', 'v4', credentials=get_credentials(scopes)).spreadsheets()
        self.raw_sheets = dict()
        metadata = self.api.get(spreadsheetId=spreadsheet_id).execute()
        sheets = metadata.get('sheets', [])
        for sheet in sheets:
            name = sheet.get("properties", {}).get("title", "Unnamed Sheet")
            sheet_id = sheet.get("properties", {}).get("sheetId", 0)
            print('Sheet title: {0}, Sheet ID: {1}'.format(name, sheet_id))
            self.raw_sheets[name] = self.api.values().get(
                spreadsheetId=self.spreadsheet_id, range=f"{name}!A1:Z"
            ).execute()



    def get_data_from_sheet(self, sheet_name, target: Union[Type, List[str]], mapping=None):
        if sheet_name not in self.raw_sheets:
            sheet_name = open_select_sheet_dialog_window(self.spreadsheet_id, sheet_name)

        data = self.raw_sheets[sheet_name].get("values", [])
        headers = data.pop(0)
        if isinstance(target, List):
            data_binding = bind_names(headers, target, '_'.join([*target, 'bindings.json']))
        else:
            data_binding = bind(headers, target)
            if mapping is None:
                mapping = lambda d: target(**d)
        if data_binding is None:
            print(f"binding column names with {target} failed")
            exit()

        values = [{k: row[v] for k, v in data_binding.items()} for row in data]
        print(values[0])
        return list(map(mapping, values)) if mapping else values
