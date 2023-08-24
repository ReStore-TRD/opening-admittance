# ReStore Opening Admittance System

## Usage

```bash
python main.py {pp,aa,dp}
```

Supports three modes:
 - Pre-Processing: This will run through all entries, and look for discrepancies and look up the various info we have on registrations.
 - Auto-Admit: This will also run the pre-processing one time, and proceed to admit the registered people randomly. Taking into account downprioritised people and people in the banlist.
 - Data Processing: This is intended to be used for for example estimating how much work our drivers will have based on people's responses.


## Setup For Use

### Configure for the right spreadsheet

Currently, the script does not provide a command line argument or UI to select which spreadsheet it should access. Instead this is defined in `main.py` in a variable `SPREADSHEET_ID`, edit this to contain the ID of your spreadsheet. This can be found in the URL when opening the spreadsheet in Google Drive.

### Required packages

This system requires the Google client library for python:

```bash
pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

### Credentials for using Google Sheets API
These scripts utilise the Google Sheets API.

For now, the way we use it lets the script act on behalf of the 
authenticated user. I.e: Upon running the script the first time, you'll 
be prompted to log in, and a credentials.json and token.json file will
be created in the working directory.

### Spreadsheet Requirements

The sheet names need to match the following
the fields names can be whatever (from the forms they are generally super long as they contain the question).

The first time the script runs on a spreadsheet it will prompt you to connect each field from these sheets to their respective meaning:
e.g: _name_ : _Write your full name as it is in your ID_

| Sheet Name                    | Required Fields                                                                                                                                     |
|-------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------|
| Responses                     | Everything from the form, at minimum: **name**, **email**, **timeslot**, **timestamp** (when the entry was made - automatically made from the form) |
| Timeslot Details              | (timeslot) name, spots, unlimited                                                                                                                   |
| Manually Confirmed Duplicates | name, email                                                                                                                                         |
| Confirmed Faulty Emails       | name, email                                                                                                                                         |
| Ban List                      | name, email                                                                                                                                         |
| Downprioritised               | name, email                                                                                                                                         |

for the 4 latter ones, you'll only be prompted once, as they use the same connections ("bindings")

## A typical use of this tool

1. Complete Setup
2. Run `python main.py pp`
3. Look through the new sheet called "Marked" and deal with entries accordingly.
4. Repeat Step 2-3 until nothing more can be done with the entries in "Marked".
5. Run `python main.py aa`. It will prompt you to type 'yes'. Do so only when you are ready to make the admission.
6. New sheets will now have been created for the admission timeslots, have a look-through to make sure everything looks OK.
7. Send out Emails
