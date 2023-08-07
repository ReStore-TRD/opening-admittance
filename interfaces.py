import tkinter as tk
import uuid
import warnings
from tkinter import simpledialog
from typing import Type, List, Optional, Dict

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from data_types import Timeslot, LimitedTimeslot
from admittance import OpeningAdmittance
from util import get_credentials


def open_create_sheet_dialog_window(spreadsheetId: str) -> Optional[str]:
    dialog_window = tk.Tk()
    dialog_window.title("Create sheet")

    sheet_name = tk.StringVar(name="sheet_name", value="")

    tk.Entry(dialog_window, textvariable=sheet_name, width=40).grid(row=0, column=0)
    tk.Button(dialog_window, text="Accept", command=dialog_window.quit).grid(row=1, column=0, columnspan=1)
    dialog_window.mainloop()

    if sheet_name.get() == "":
        warnings.warn("Sheet name cannot be empty")
        return None

    try:
        service = build('sheets', 'v4', credentials=get_credentials(["https://www.googleapis.com/auth/spreadsheets"]))
        # Call the Sheets API
        spreadsheet = {'properties': {'title': sheet_name.get()}}
        spreadsheet = service.spreadsheets().create(body=spreadsheet, fields='spreadsheetId').execute()
        return spreadsheet["properties"]["title"]
    except HttpError as e:
        warnings.warn(str(e))
        return None


def open_select_sheet_dialog_window(spreadsheetId: str) -> Optional[str]:

    try:
        service = build('sheets', 'v4', credentials=get_credentials(["https://www.googleapis.com/auth/spreadsheets"]))
        # Get all sheets in the spreadsheet
        sheets = service.spreadsheets().get(spreadsheetId=spreadsheetId, fields="sheets.properties").execute()["sheets"]
    except HttpError as e:
        warnings.warn(str(e))
        return None

    sheet_names = [sheet["properties"]["title"] for sheet in sheets]

    dialog_window = tk.Tk()
    dialog_window.title("Select sheet")
    sheet_name = tk.StringVar(name="sheet_name", value="Select a sheet...")

    def create_sheet():
        dialog_window.destroy()
        new_sheet_name = open_create_sheet_dialog_window(spreadsheetId)
        sheet_names.append(new_sheet_name)
        sheet_name.set(new_sheet_name)


    tk.OptionMenu(dialog_window, sheet_name, *sheet_names).grid(row=0, column=0, columnspan=2)
    tk.Button(dialog_window, text="Accept", command=dialog_window.quit).grid(row=1, column=0)
    tk.Button(dialog_window, text="Create", command=create_sheet).grid(row=1, column=1)
    dialog_window.mainloop()

    if sheet_name.get() in sheet_names:
        return sheet_name.get()
    return None


def open_spreadsheet_dialog_window(title: str, default_value: str) -> Optional[str]:
    dialog_window = tk.Tk()
    dialog_window.title(title)
    cancel = False
    return_val = None

    def cancel_dialog():
        nonlocal cancel
        cancel = True
        dialog_window.destroy()

    tk.Label(dialog_window, text="Enter Google Spreadsheet URL:").grid(row=0, column=0, padx=(10, 5))
    spreadsheet_url = tk.StringVar(name="spreadsheet_url", value=default_value)
    tk.Entry(dialog_window, textvariable=spreadsheet_url, width=40).grid(row=0, column=1, padx=(5, 10))
    tk.Button(dialog_window, text="Accept", command=dialog_window.quit).grid(row=1, column=0, columnspan=1)
    tk.Button(dialog_window, text="Cancel", command=cancel_dialog).grid(row=1, column=1, columnspan=1)

    dialog_window.protocol("WM_DELETE_WINDOW", cancel_dialog)
    dialog_window.mainloop()

    if not cancel:
        # return the spreadsheet ID
        return_val = spreadsheet_url.get().split("spreadsheets/d/")[-1].split("/")[0]

    return return_val


def open_admittance_creation_window():
    create_admittance_window = tk.Tk()
    create_admittance_window.title("Create Opening Admittance")

    variable_sets = [{
        "start_hour": tk.StringVar(name="start_hour", value="10"),
        "start_minute": tk.StringVar(name="start_minute", value="00"),
        "end_hour": tk.StringVar(name="end_hour", value="11"),
        "end_minute": tk.StringVar(name="end_minute", value="00"),
        "unlimited": tk.BooleanVar(name="unlimited", value=False),
        "num_slots": tk.IntVar(name="num_slots", value=40),
    }]

    # Create a list and a button to add new items to the list
    tk.Label(create_admittance_window, text="Timeslots").grid(row=0, column=0)
    (listbox_frame := tk.Frame(create_admittance_window)).grid(row=1, column=0)
    (listbox := tk.Listbox(listbox_frame, selectmode=tk.SINGLE)).grid(row=1, column=0, columnspan=2)
    listbox.insert(tk.END, f"{variable_sets[0]['start_hour'].get()}:{variable_sets[0]['start_minute'].get()}-"
                           f"{variable_sets[0]['end_hour'].get()}:{variable_sets[0]['end_minute'].get()} ")
    listbox.select_set(0)

    def time_changed():
        index = listbox.curselection()[0]
        time_str = f"{variable_sets[index]['start_hour'].get()}:{variable_sets[index]['start_minute'].get()}-" \
                   f"{variable_sets[index]['end_hour'].get()}:{variable_sets[index]['end_minute'].get()}"
        listbox.delete(index)
        listbox.insert(index, time_str)
        listbox.select_set(index)
        change_selected_timeslot(index)

    timeslot_frame = tk.Frame(create_admittance_window, bd=1, relief=tk.SUNKEN)
    timeslot_frame.grid(row=1, column=2, sticky=tk.NSEW)

    tk.Label(timeslot_frame, text="Start time").grid(row=0, column=0, sticky=tk.W)
    (start_time_frame := tk.Frame(timeslot_frame)).grid(row=0, column=1)
    tk.Label(start_time_frame, text="h").grid(row=0, column=0)
    start_time_hour_spinbox = tk.Spinbox(start_time_frame, from_=0, to=23, format="%02.0f",
                                         textvariable=variable_sets[0]["start_hour"], wrap=True, width=3,
                                         command=time_changed)
    start_time_hour_spinbox.grid(row=0, column=1)
    tk.Label(start_time_frame, text="m").grid(row=0, column=2)
    start_time_minute_spinbox = tk.Spinbox(start_time_frame, from_=0, to=59, increment=5, format="%02.0f",
                                           textvariable=variable_sets[0]["start_minute"], wrap=True, width=3,
                                           command=time_changed)
    start_time_minute_spinbox.grid(row=0, column=3)

    tk.Label(timeslot_frame, text="End time").grid(row=1, column=0, sticky=tk.W)
    (end_time_frame := tk.Frame(timeslot_frame)).grid(row=1, column=1)
    tk.Label(end_time_frame, text="h").grid(row=0, column=0)
    end_time_hour_spinbox = tk.Spinbox(end_time_frame, from_=0, to=23, format="%02.0f",
                                       textvariable=variable_sets[0]["end_hour"], wrap=True, width=3,
                                       command=time_changed)
    end_time_hour_spinbox.grid(row=0, column=1)
    tk.Label(end_time_frame, text="m").grid(row=0, column=2)
    end_time_minute_spinbox = tk.Spinbox(end_time_frame, from_=0, to=59, increment=5, format="%02.0f",
                                         textvariable=variable_sets[0]["end_minute"], wrap=True, width=3,
                                         command=time_changed)
    end_time_minute_spinbox.grid(row=0, column=3)

    tk.Label(timeslot_frame, text="Number of slots").grid(row=4, column=0, sticky=tk.W)
    num_slots_spinbox = tk.Spinbox(timeslot_frame, from_=0, to=100, textvariable=variable_sets[0]["num_slots"], width=3)
    num_slots_spinbox.grid(row=4, column=1, sticky=tk.W, padx=13)

    def change_unlimited():
        index = listbox.curselection()[0]
        if variable_sets[index]["unlimited"].get():
            num_slots_spinbox.configure(state="disabled")
        else:
            num_slots_spinbox.configure(state="normal")

    tk.Label(timeslot_frame, text="Unlimited slots").grid(row=3, column=0, sticky=tk.W)
    unlimited_checkbox = tk.Checkbutton(timeslot_frame, variable=variable_sets[0]["unlimited"],
                                        command=change_unlimited)
    unlimited_checkbox.grid(row=3, column=1, sticky=tk.W, padx=8)

    def change_selected_timeslot(event_args):
        index = listbox.curselection()[0]
        start_time_hour_spinbox.config(textvariable=variable_sets[index]["start_hour"])
        start_time_minute_spinbox.config(textvariable=variable_sets[index]["start_minute"])
        end_time_hour_spinbox.config(textvariable=variable_sets[index]["end_hour"])
        end_time_minute_spinbox.config(textvariable=variable_sets[index]["end_minute"])
        unlimited_checkbox.config(variable=variable_sets[index]["unlimited"])
        num_slots_spinbox.config(textvariable=variable_sets[index]["num_slots"])
        change_unlimited()

    def new_timeslot():
        timeslot = listbox.get(tk.END)
        end_time = timeslot.split("-")[1]
        end_hour, end_minute = end_time.split(":")
        guid = uuid.uuid1()
        variable_sets.append({
            "start_hour": tk.StringVar(name=f"{guid}start_hour", value=end_hour),
            "start_minute": tk.StringVar(name=f"{guid}start_minute", value=end_minute),
            "end_hour": tk.StringVar(name=f"{guid}end_hour", value=str(int(end_hour) + 1)),
            "end_minute": tk.StringVar(name=f"{guid}end_minute", value=end_minute),
            "unlimited": tk.BooleanVar(name=f"{guid}unlimited", value=False),
            "num_slots": tk.IntVar(name=f"{guid}num_slots", value=40),
        })
        time_str = "{:02d}:{:02d}-{:02d}:{:02d}".format(int(end_hour), int(end_minute), int(end_hour) + 1,
                                                        int(end_minute))
        listbox.insert(tk.END, time_str)

    def remove_timeslot():
        if listbox.size() == 1:
            return
        index = listbox.curselection()[0]
        variable_sets.pop(index)
        print("pop", index)
        listbox.delete(index)
        if index == listbox.size():
            index -= 1
        listbox.select_set(index)
        change_selected_timeslot(None)

    listbox.bind('<<ListboxSelect>>', change_selected_timeslot)

    tk.Button(listbox_frame, text="Add", command=new_timeslot, width=7).grid(row=2, column=0, sticky=tk.NSEW)
    # Create a button to remove the selected item from the list
    tk.Button(listbox_frame, text="Remove", command=remove_timeslot, width=7).grid(row=2, column=1, sticky=tk.NSEW)

    # spacing
    tk.Frame(create_admittance_window, height=10).grid(row=3, column=0, columnspan=4, sticky=tk.NSEW)

    # Create a button to accept the list and close the window
    tk.Button(create_admittance_window, text="Accept", command=create_admittance_window.quit).grid(row=4, column=0,
                                                                                                   columnspan=3,
                                                                                                   sticky=tk.NSEW,
                                                                                                   padx=80, pady=10)
    # TODO: deal with the window being closed without accepting
    # create_admittance_window.protocol("WM_DELETE_WINDOW", cancel_dialog)

    create_admittance_window.mainloop()

    # Create the admittance from current state upon exiting the window

    timeslots = {}
    for i in range(listbox.size()):
        if variable_sets[i]["unlimited"].get():
            timeslot = Timeslot()
        else:
            timeslot = LimitedTimeslot(variable_sets[i]["num_slots"].get())
        timeslots[listbox.get(i)] = timeslot

    return OpeningAdmittance(timeslots)


def open_column_name_binding_window(datatype: Type, column_names: List[str]) -> Optional[Dict[str, int]]:
    # Get constructor arguments, excluding self
    args = datatype.__init__.__code__.co_varnames[1:]

    binding_window = tk.Tk()
    binding_window.title("Field binding")

    binding_vars = {arg: tk.StringVar(name=arg, value="Select a column...") for arg in args}

    for i, arg in enumerate(args):
        tk.Label(binding_window, text=arg).grid(row=i, column=0)
        tk.OptionMenu(binding_window, binding_vars[arg], *column_names).grid(row=i, column=3)

    tk.Button(binding_window, text="Accept", command=binding_window.quit).grid(row=len(args), column=1, columnspan=2)
    binding_window.mainloop()

    bindings = {arg: column_names.index(binding_vars[arg].get()) for arg in args if
                binding_vars[arg].get() in column_names}
    from binding import verify_column_bindings
    if verify_column_bindings(datatype, bindings):
        return bindings
    return None
