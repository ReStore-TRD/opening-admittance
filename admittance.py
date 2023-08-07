import csv
import os
from collections import defaultdict
from datetime import datetime
from typing import Dict, Set, DefaultDict, List, Optional, Iterable

from googleapiclient.discovery import build

from data_types import Person, Registration, Timeslot
from util import get_credentials


class OpeningAdmittance:
    timeslots: Dict[str, Timeslot]
    processed: Dict[Person, Registration]
    cancelled: Set[Person]
    banned: Set[Person]
    marked: DefaultDict[Person, List[str]]
    confirmed_duplicates: Set[Person]
    confirmed_nonworking_email: Set[Person]

    def __init__(self, timeslots: Optional[Dict[str, Timeslot]] = None):
        self.timeslots = timeslots if timeslots else {}
        self.waiting_list = []
        self.cancelled = set()
        self.banned = set()
        self.marked = defaultdict(list)
        self.confirmed_duplicates = set()
        self.confirmed_nonworking_email = set()

    def _preprocess_and_mark(self, registrations: Iterable[Registration]):
        """
        Look through all regisstrations beforehand to mark individuals for manual checking if needed
        and overwrite duplicate registrations by the latest entry from said person if the latest entry makes changes
        to their preferences in timeslot
        :param registrations: All entries from the registration form
        :return: registrations without duplicate entries (NOTE: suspected duplicates are only marked for manual check
                 and will remain as separate registrations)
        """
        bad_email_endings = [".con", "@ntnu.no"]

        proccessed_for_admission = {}
        for registration in registrations:

            # Evaluate if peron is banned
            if registration.person in self.banned:
                self.marked[registration.person].append("Banned from attending, see ban list!")
                continue
            else:
                confirmed_duplicate = False
                for banned_person in self.banned:
                    if banned_person.similar(registration.person):
                        if confirmed_duplicate := registration.person in self.confirmed_duplicates:
                            self.marked[registration.person].append(f"Confirmed ban, see ban list for {banned_person}!")
                            self.banned.add(registration.person)
                            break
                        else:
                            self.marked[registration.person].append(f"Suspected ban: {registration.person} might be!, "
                                                                    f"{banned_person} from banlist!")
                            break
                if confirmed_duplicate:
                    continue  # skip this person, go on to the next!

            # Evaluate if person has a bad email ending
            for ending in bad_email_endings:
                if registration.person.email.endswith(ending):
                    self.marked[registration.person].append(f"Likely a non-working email! It ends with '{ending}'.")

            # Evaluate if person has not been given a timeslot because of attending previous "premium" timeslots in
            # earlier opening
            if all(registration.person in timeslot.disallowed for timeslot in self.timeslots.values()):
                self.marked[registration.person].append(
                    "Down prioritised from attending the timeslot(s) they signed up for, "
                    "attended previous opening in the early slot(s)!"
                )
                continue  # go on to the next person!

            for timeslot_name, timeslot in self.timeslots.items():
                if timeslot_name not in registration.timeslots:  # we only care if they signed this timeslot
                    continue
                if registration.person in timeslot.disallowed:
                    self.marked[registration.person].append(
                        f"Down prioritised from attending {timeslot_name} because they "
                        f"attended previous opening in the early slot(s)!"
                    )
                    break
                else:
                    # confirmed_duplicate = False
                    for downprioritised_person in timeslot.disallowed:
                        if downprioritised_person.similar(registration.person):
                            if confirmed_duplicate := registration.person in self.confirmed_duplicates:
                                self.marked[registration.person].append(
                                    f"Down prioritised from attending {timeslot_name} because they "
                                    "attended previous opening in the early slot(s)!. confirmed suspected duplicate"
                                    f" of: {downprioritised_person} from downprioritised list!"
                                )
                                timeslot.disallowed.add(registration.person)
                                break
                            else:
                                self.marked[registration.person].append(
                                    f"Subject to being down prioritised from {timeslot_name}, "
                                    f"suspecting {registration.person} might be the"
                                    f"same as {downprioritised_person} from the down prioritised list!"
                                )
                                break
                    # if confirmed_duplicate:
                    #     continue  # skip this person, go on to the next!

            # Evaluate if person is already in the system
            if (person := registration.person) in proccessed_for_admission.keys():
                # only overwrite entry if change in timeslots
                if set(registration.timeslots) != set(proccessed_for_admission[person].timeslots):
                    # NOTE: changing your timeslots has its drawback - you're now later in the queue
                    reason = f"Duplicate Entry for {person}:\noverwriting {proccessed_for_admission[person]}...\n" \
                             f"timestamp changed from {proccessed_for_admission[person].timestamp} to {registration.timestamp}\n" \
                             f"changed timeslots from {proccessed_for_admission[person].timeslots} to {registration.timeslots}"
                    self.marked[person].append(reason)
                else:
                    # if no substantial change is made, don't reprocess the person. They did as intended the first
                    # time around and should not be punished for trying to make sure they registered.
                    continue
            else:
                for already_processed_person, already_processed_registration in proccessed_for_admission.copy().items():
                    if registration.person.similar(already_processed_person):
                        if confirmed_duplicate := registration.person in self.confirmed_duplicates:
                            # only overwrite entry if change in timeslots
                            self.marked[already_processed_person].append(
                                f"Confirmed suspected duplicate! {registration.person} is the same as {already_processed_person}!"
                                f"\nOverwriting {already_processed_registration} with {registration}...\n"
                            )
                            del proccessed_for_admission[already_processed_person]
                        else:
                            self.marked[already_processed_person].append(f"Suspected duplicate of {registration}")
                            self.marked[registration.person].append(
                                f"Suspected duplicate of {already_processed_registration}")
                            break

            # Evaluate if person has a confirmed non-working email
            if registration.person in self.confirmed_nonworking_email:
                self.marked[registration.person].append("Confirmed non-working email!")
                continue # go on to the next person!

            proccessed_for_admission[person] = registration
        return proccessed_for_admission

    def auto_admit(self, registrations: Iterable[Registration]):
        self.processed = self._preprocess_and_mark(registrations)
        for registration in self.processed.values():
            if not any(self.timeslots[wanted_slot].admit(registration) for wanted_slot in registration.timeslots if
                       wanted_slot in self.timeslots):
                self.waiting_list.append(registration)

    def write_to_csv(self):
        os.makedirs("./output/", exist_ok=True)
        for name, timeslot in self.timeslots.items():
            with open(f"./output/{name.replace(':', '')}.csv", 'w', newline='', encoding="utf-8") as file:
                if not timeslot.spots:
                    continue
                fields = timeslot.spots[0].__dict__.keys()
                writer = csv.DictWriter(file, fields)
                writer.writeheader()
                for registration in timeslot.spots:
                    writer.writerow({k: v for k, v in registration.__dict__.items() if k in fields})

        with open(f"./output/waiting_list.csv", 'w', newline='', encoding="utf-8") as file:
            if not self.waiting_list:
                return
            fields = self.waiting_list[0].__dict__.keys()
            writer = csv.DictWriter(file, fields)
            writer.writeheader()
            for registration in self.waiting_list:
                writer.writerow({k: v for k, v in registration.__dict__.items() if k in fields})

        with open(f"./output/marked.csv", 'w', newline='', encoding="utf-8") as file:
            if not self.marked:
                return
            marked_list = [(reg.person, reason) for reg, reason in self.marked.items()]
            fields = [*marked_list[0][0].__dict__.keys(), "marked reason"]
            writer = csv.DictWriter(file, fields)
            writer.writeheader()
            for person, reason in marked_list:
                entry = {k: v for k, v in person.__dict__.items() if k in fields}
                entry["marked reason"] = reason
                writer.writerow(entry)

    def write_to_spreadsheet(self, spreadsheetId: str):
        service = build('sheets', 'v4', credentials=get_credentials(["https://www.googleapis.com/auth/spreadsheets"]))
        sheet = service.spreadsheets()
        # create or clear sheet for each timeslot

        sheet_metadata = sheet.get(spreadsheetId=spreadsheetId).execute()
        sheets = sheet_metadata.get('sheets', '')
        sheet_names = [sheet.get("properties", {}).get("title", "") for sheet in sheets]

        for name, timeslot in self.timeslots.items():
            if not timeslot.spots: # No one is attending this timeslot
                continue
            # check if spreadsheet with name exists
            if name in sheet_names:
                # clear sheet
                sheet.values().clear(spreadsheetId=spreadsheetId, range=f"{name}!A1:Z").execute()
            else:
                # create sheet
                sheet.batchUpdate(spreadsheetId=spreadsheetId, body={"requests": [{"addSheet": {"properties": {"title": name}}}]}).execute()
                sheet_names.append(name)

            # write to sheet
            fields = list(timeslot.spots[0].__dict__.keys())
            values = [fields]
            for registration in timeslot.spots:
                values.append([str(getattr(registration, field)) for field in fields])
            body = {
                'values': values
            }
            sheet.values().update(spreadsheetId=spreadsheetId, range=f"{name}!A1:Z", valueInputOption="USER_ENTERED", body=body).execute()

        # write to waiting list sheet
        if self.waiting_list:
            # create or clear waiting list sheet
            if "waiting_list" in sheet_names:
                # clear sheet
                sheet.values().clear(spreadsheetId=spreadsheetId, range=f"waiting_list!A1:Z").execute()
            else:
                # create sheet
                sheet.batchUpdate(spreadsheetId=spreadsheetId, body={"requests": [{"addSheet": {"properties": {"title": "waiting_list"}}}]}).execute()
                sheet_names.append("waiting_list")

            fields = list(self.waiting_list[0].__dict__.keys())
            values = [fields]
            for registration in self.waiting_list:
                values.append([str(getattr(registration, field)) for field in fields])
            body = {
                'values': values
            }
            sheet.values().update(spreadsheetId=spreadsheetId, range=f"waiting_list!A1:Z", valueInputOption="USER_ENTERED", body=body).execute()

        # write to marked sheet
        if self.marked:
            # create or clear marked sheet
            if "marked" in sheet_names:
                # clear sheet
                sheet.values().clear(spreadsheetId=spreadsheetId, range=f"marked!A1:Z").execute()
            else:
                # create sheet
                sheet.batchUpdate(spreadsheetId=spreadsheetId, body={"requests": [{"addSheet": {"properties": {"title": "marked"}}}]}).execute()
                sheet_names.append("marked")

            marked_list = [(reg.person, reason) for reg, reason in self.marked.items()]
            fields = [*list(marked_list[0][0].__dict__.keys()), "marked reason"]
            print(fields)
            values = [fields]
            for person, reason in marked_list:
                entry = [str(getattr(person, field)) for field in fields[:-1]]
                entry.append('\n'.join(reason))
                values.append(entry)
            body = {
                'values': values
            }
            print(body)
            sheet.values().update(spreadsheetId=spreadsheetId, range=f"marked!A1:Z", valueInputOption="USER_ENTERED", body=body).execute()
