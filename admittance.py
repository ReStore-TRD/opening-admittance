import random
from collections import defaultdict
from typing import Dict, Set, DefaultDict, List, Optional, Iterable, Collection

from googleapiclient.discovery import build

from data_types import Person, Registration, Timeslot, LimitedTimeslot
from spreadsheet_reader import SpreadsheetReader
from util import get_credentials


# TODO: Sort marked by marked reason
#

def _normalise(field: str) -> str:
    return field.lower().strip()

class OpeningAdmittance:
    timeslots: Dict[str, Timeslot]
    processed: Dict[Person, Registration]
    cancelled: Set[Person]
    banned: Set[Person]
    marked: DefaultDict[Person, List[str]]
    confirmed_duplicates: Set[Person]
    confirmed_nonworking_emails: Set[Person]
    all_registrations: Collection[Registration]

    def __init__(self, timeslots: Optional[Dict[str, Timeslot]] = None, registrations: Optional[Collection[Registration]] = None):
        self.timeslots = timeslots if timeslots else {}
        self.waiting_list = []
        self.cancelled = set()
        self.banned = set()
        self.marked = defaultdict(list)
        self.confirmed_duplicates = set()
        self.confirmed_nonworking_emails = set()
        self.all_registrations = registrations

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
                self.marked[registration.person].append("[DONE]\nBanned from attending, see ban list!")
                continue
            else:
                confirmed_duplicate = False
                for banned_person in self.banned:
                    if banned_person.similar(registration.person):
                        # if similarity manually confirmed as match
                        if confirmed_duplicate := registration.person in self.confirmed_duplicates:
                            self.marked[registration.person].append(f"[DONE]\nConfirmed ban, see ban list for {banned_person}!")
                            self.banned.add(registration.person)
                            break
                        else:
                            self.marked[registration.person].append(f"[NEED CONFIRMATION]\nSuspected ban: {registration.person} might be!, "
                                                                    f"{banned_person} from banlist!")
                            break
                if confirmed_duplicate:
                    continue  # skip this person, go on to the next!

            # Evaluate if person has a bad email ending
            for ending in bad_email_endings:
                if registration.person.email.endswith(ending):
                    self.marked[registration.person].append(
                        "[UNCONFIRMED] (if anything can be done about it, do so, otherwise it'll be discovered upon "
                        f"sending out emails)\nLikely a non-working email! It ends with '{ending}'.")

            # Evaluate if person has not been given a timeslot because of attending previous "premium" timeslots in
            # earlier opening
            if all(registration.person in timeslot.disallowed for timeslot in self.timeslots.values()):
                self.marked[registration.person].append(
                    "[DONE]\nDown prioritised from attending the timeslot(s) they signed up for, "
                    "attended previous opening in the early slot(s)!"
                )
                continue  # go on to the next person!

            for timeslot_name, timeslot in self.timeslots.items():
                if timeslot_name not in registration.timeslots:  # we only care if they signed this timeslot
                    continue
                if registration.person in timeslot.disallowed:
                    self.marked[registration.person].append(
                        f"[DONE]\nDown prioritised from attending {timeslot_name} because they "
                        f"attended previous opening in the early slot(s)!"
                    )
                    break
                else:
                    # confirmed_duplicate = False
                    for downprioritised_person in timeslot.disallowed:
                        if downprioritised_person.similar(registration.person):
                            if confirmed_duplicate := registration.person in self.confirmed_duplicates:
                                self.marked[registration.person].append(
                                    f"[DONE]\nDown prioritised from attending {timeslot_name} because they "
                                    "attended previous opening in the early slot(s)!. confirmed duplicate"
                                    f" of: {downprioritised_person} from downprioritised list!"
                                )
                                timeslot.disallowed.add(registration.person)
                                break
                            else:
                                self.marked[registration.person].append(
                                    "[NEED CONFIRMATION]\nSuspected duplicate of previous attendance!, "
                                    f"{registration.person} might be the same as"
                                    f"{downprioritised_person} from the downprioritised list!"
                                    f"this will move them out of timeslot {timeslot_name}"
                                )
                                break
                    # if confirmed_duplicate:
                    #     continue  # skip this person, go on to the next!

            # Evaluate if person is already in the system
            if (person := registration.person) in proccessed_for_admission.keys():
                # only overwrite entry if change in timeslots
                if set(registration.timeslots) != set(proccessed_for_admission[person].timeslots):
                    # NOTE: changing your timeslots has its drawback - you're now later in the queue
                    reason = "[DONE] (confirmed exact match by script)\n" \
                             f"Duplicate Entry for {person}:\noverwriting {proccessed_for_admission[person]}...\n" \
                             f"timestamp changed from {proccessed_for_admission[person].timestamp} to {registration.timestamp}\n" \
                             f"changed timeslots from {proccessed_for_admission[person].timeslots} to {registration.timeslots}"
                    self.marked[person].append(reason)
                else:
                    reason = "[DONE] (confirmed exact match by script)\n" \
                             f"Confirmed duplicate for {person}:\n{proccessed_for_admission[person]} will be used...\n"
                    self.marked[person].append(reason)
                    # if no substantial change is made, don't reprocess the person. They did as intended the first
                    # time around and should not be punished for trying to make sure they registered.
                    continue
            else:
                for already_processed_person, already_processed_registration in proccessed_for_admission.copy().items():
                    if registration.person.similar(already_processed_person):
                        if confirmed_duplicate := registration.person in self.confirmed_duplicates:
                            # only overwrite entry if change in timeslots
                            self.marked[already_processed_person].append(
                                "[DONE] (Manually confirmed)\nDuplicate: "
                                f"{registration.person} is the same as {already_processed_person}!"
                                f"\nOverwriting {already_processed_registration} with {registration}...\n"
                            )
                            del proccessed_for_admission[already_processed_person]
                        else:
                            self.marked[already_processed_person].append(
                                "[NEED CONFIRMATION] (if confirmed, put entries in Confirmed Duplicates)\n"
                                f"Suspected duplicate of {registration}")
                            self.marked[registration.person].append(
                                "[NEED CONFIRMATION] (if confirmed, put entries in Confirmed Duplicates)\n"
                                f"Suspected duplicate of {already_processed_registration}")
                            break

            # Evaluate if person has a confirmed non-working email
            if registration.person in self.confirmed_nonworking_emails:
                self.marked[registration.person].append("[DONE] (manually confirmed)\nConfirmed non-working email!")
                continue # go on to the next person!

            proccessed_for_admission[person] = registration
        return proccessed_for_admission

    def preprocess(self):
        print("Preprocessing...")
        self.processed = self._preprocess_and_mark(self.all_registrations)

    def auto_admit(self):
        print("Admitting...")
        if len(self.processed) == 0:
            print("No registrations have been preprocessed, this needs to be done beforehand!")
            return
        unadmitted = set(self.processed.values())
        admitted = set()

        for timeslot_handle, timeslot in self.timeslots.items():
            # make a lottery pool from the registrations
            # filter out registrations that have not chosen this timeslot and those who have already been admitted
            lottery_pool = [reg for reg in unadmitted if timeslot_handle in reg.timeslots and reg not in admitted]
            while len(lottery_pool) > 0:
                drawn = random.choice(lottery_pool)
                lottery_pool.remove(drawn)
                if timeslot.admit(drawn):
                    admitted.add(drawn)

        unadmitted.difference_update(admitted)
        if len(unadmitted) > 0:
            # This is the master waiting list, with all unadmitted people
            self.waiting_list.extend(unadmitted)

    def write_to_spreadsheet(self, spreadsheetId: str, write_timeslots=True, write_marked=True):
        print("Writing to spreadsheets...")

        service = build('sheets', 'v4', credentials=get_credentials(["https://www.googleapis.com/auth/spreadsheets"]))
        sheet = service.spreadsheets()
        # create or clear sheet for each timeslot

        sheet_metadata = sheet.get(spreadsheetId=spreadsheetId).execute()
        sheets = sheet_metadata.get('sheets', '')
        sheet_names = [sheet.get("properties", {}).get("title", "") for sheet in sheets]

        if write_timeslots:
            for name, timeslot in self.timeslots.items():
                if not timeslot.spots: # No one is attending this timeslot
                    print("No timeslot spots used for", name)
                    continue
                # check if spreadsheet with name exists
                if name in sheet_names:
                    # clear sheet
                    sheet.values().clear(spreadsheetId=spreadsheetId, range=f"{name}!A1:Z").execute()
                else:
                    # create sheet
                    print("Create new sheet!", spreadsheetId)
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

                if not isinstance(timeslot, LimitedTimeslot):
                    continue
                # Timeslot is a limited one, let's write the waiting list to a sheet too
                timeslot: LimitedTimeslot

                # write to waiting list sheet
                if self.waiting_list:
                    # create or clear waiting list sheet
                    if "waiting_list" in sheet_names:
                        # clear sheet
                        sheet.values().clear(spreadsheetId=spreadsheetId, range=f"waiting_list!A1:Z").execute()
                    else:
                        # create sheet
                        sheet.batchUpdate(spreadsheetId=spreadsheetId, body={
                            "requests": [{"addSheet": {"properties": {"title": "waiting_list"}}}]}).execute()
                        sheet_names.append("waiting_list")

                    fields = list(self.waiting_list[0].__dict__.keys())
                    values = [fields]
                    for registration in self.waiting_list:
                        values.append([str(getattr(registration, field)) for field in fields])
                    body = {
                        'values': values
                    }
                    sheet.values().update(spreadsheetId=spreadsheetId, range=f"waiting_list!A1:Z",
                                          valueInputOption="USER_ENTERED", body=body).execute()

                #waiting_list_name = f"{name}_waitinglist"
                #if waiting_list_name in sheet_names:
                #    # clear sheet
                #    sheet.values().clear(spreadsheetId=spreadsheetId, range=f"{waiting_list_name}!A1:Z").execute()
                #else:
                #    # create sheet
                #    sheet.batchUpdate(spreadsheetId=spreadsheetId,
                #                      body={"requests": [{"addSheet": {"properties": {"title": waiting_list_name}}}]}).execute()
                #    sheet_names.append(waiting_list_name)
#
                ## write to sheet
                #fields = list(timeslot.waiting_list[0].__dict__.keys())
                #values = [fields]
                #for registration in timeslot.spots:
                #    values.append([str(getattr(registration, field)) for field in fields])
                #body = {
                #    'values': values
                #}
                #sheet.values().update(spreadsheetId=spreadsheetId, range=f"{waiting_list_name}!A1:Z", valueInputOption="USER_ENTERED", body=body).execute()

        if write_marked:
            # write to marked sheet
            if self.marked:
                # create or clear marked sheet
                if "Marked" in sheet_names:
                    # clear sheet
                    sheet.values().clear(spreadsheetId=spreadsheetId, range=f"Marked!A1:Z").execute()
                else:
                    # create sheet
                    # TODO: Insert conditional formatting rules for patterns like '=SEARCH("[NEED CONFIRMATION]", $C2)'
                    sheet.batchUpdate(spreadsheetId=spreadsheetId, body={"requests": [{"addSheet": {"properties": {"title": "Marked"}}}]}).execute()
                    sheet_names.append("marked")

                marked_list = [(reg.person, reason) for reg, reason in self.marked.items()]
                fields = [*list(marked_list[0][0].__dict__.keys()), "marked reason"]
                values = [fields]
                for person, reason in marked_list:
                    entry = [str(getattr(person, field)) for field in fields[:-1]]
                    entry.append('\n'.join(reason))
                    values.append(entry)
                body = {
                    'values': values
                }
                sheet.values().update(spreadsheetId=spreadsheetId, range=f"marked!A1:Z", valueInputOption="USER_ENTERED", body=body).execute()

            #
            # sheet.values().clear(spreadsheetId=spreadsheetId, range=f"{name}!A1:Z1000").execute()
            #
            #
            # if not timeslot.spots:
            #     continue
            # fields = timeslot.spots[0].__dict__.keys()
            # values = [fields]
            # for registration in timeslot.spots:
            #     values.append([v for k, v in registration.__dict__.items() if k in fields])
            # body = {
            #     'values': values
            # }
            # # sheet.values().update(spreadsheetId=spreadsheetId, range=f"{name}!A1", valueInputOption="USER_ENTERED", body=body).execute()

    @classmethod
    def read_from_spreadsheet(cls, spreadsheet_id: str):

        reader = SpreadsheetReader(spreadsheet_id, ['https://www.googleapis.com/auth/spreadsheets'])
        all_reg = reader.get_data_from_sheet(
            "Responses", ["name", "email", "location", "want_delivery"],
            lambda d: {'name': _normalise(d['name']), 'email': _normalise(d['email']), 'location': d['location'], 'want_delivery': True if "Yes" in d['want_delivery'] else False}
        )
        all_reg = {Person.from_dict(d): d for d in all_reg}

        timeslots = [
            reader.get_data_from_sheet("10:00-11:00", Person),
            reader.get_data_from_sheet("11:00-12:00", Person),
            reader.get_data_from_sheet("12:00-13:00", Person),
        ]

        print('\n\n\n\n', timeslots[0], len(timeslots[0]), '\n\n\n\n')
        # set of all people for each timeslot combined
        admitted = {p for timeslot in timeslots for p in timeslot}

        # registrations for all people who were admitted
        admitted_reg = [all_reg[person] for person in admitted]

        # ======================== TEMP ========================
        service = build('sheets', 'v4', credentials=get_credentials(["https://www.googleapis.com/auth/spreadsheets"]))
        sheet = service.spreadsheets()
        sheet_metadata = sheet.get(spreadsheetId=spreadsheet_id).execute()
        sheets = sheet_metadata.get('sheets', '')
        sheet_names = [sheet.get("properties", {}).get("title", "") for sheet in sheets]

        name = "All Admitted"
        if name in sheet_names:
            # clear sheet
            sheet.values().clear(spreadsheetId=spreadsheet_id, range=f"{name}!A1:Z").execute()
        else:
            # create sheet
            sheet.batchUpdate(spreadsheetId=spreadsheet_id,
                              body={"requests": [{"addSheet": {"properties": {"title": name}}}]}).execute()
            sheet_names.append(name)

        # write to sheet
        fields = ['name', 'email']
        values = [fields]
        for registration in all_reg:
            values.append([str(getattr(registration, field)) for field in fields])
        body = {
            'values': values
        }
        sheet.values().update(spreadsheetId=spreadsheet_id, range=f"{name}!A1:Z", valueInputOption="USER_ENTERED",
                              body=body).execute()
        # ======================== TEMP ========================

        want_delivery = 0
        location = defaultdict(int)
        for reg in admitted_reg:
            if reg['want_delivery']:
                want_delivery += 1
                location[reg['location']] += 1

        print(f"People who want delivery: {want_delivery}\nDelivery Locations:")
        for l, n in location.items():
            print(f"\t{l}: {n} deliveries")

