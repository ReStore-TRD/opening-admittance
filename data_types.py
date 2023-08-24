from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from itertools import permutations
from typing import List, Dict, Set, DefaultDict, Optional, Union
from datetime import datetime

def _seq_ignore_space(c: str):
    return c in " \t\r\n"

def _normalise(field: str) -> str:
    return field.lower().strip()

@dataclass(frozen=True, eq=True)
class Person:
    name: str
    email: str

    @property
    def person(self):
        return Person(self.name, self.email)

    def similar(self, other: Person, similarity_threshold: float = 0.9) -> bool:
        # Consider permutations of name order, last name before first name etc.

        email_similarity = SequenceMatcher(_seq_ignore_space, self.email, other.email).ratio()
        if email_similarity > similarity_threshold:
            return True

        # Evaluate all permutations of other's name consisting of same number of sub-names as self
        #   Example:    self:   Ola Nordmann
        #               other:  Per Nordmann Ola
        #       This will make permutations of other of length: len("Ola Nordmann".split(' ')) = 2
        #       Permutations made: (Per Nordmann, Per Ola, Nordmann Per, Nordmann Ola, Ola Per, Ola Nordmann)

        name_similarity = 0
        num_sub_names = len(self.name.split(' '))
        seqm = SequenceMatcher(_seq_ignore_space, self.name)
        for name in (' '.join(name_part) for name_part in permutations(other.name.split(' '), num_sub_names)):
            seqm.set_seq2(name)
            if seqm.quick_ratio() < similarity_threshold:  # skip if sets of character doesn't match enough
                continue
            if (ratio := seqm.ratio()) > name_similarity:
                name_similarity = ratio
                if name_similarity > similarity_threshold:
                    return True
        return False

    @classmethod
    def from_dict(cls, data: dict):
        return cls(_normalise(data['name']), _normalise(data['email']))


@dataclass(frozen=True)
class Registration(Person):
    timestamp: datetime.datetime = field(compare=False)
    timeslots: [str] = field(compare=False)

    def __eq__(self, other: Registration):
        return self.person.__eq__(other.person)

    @property
    def registration(self):
        return Registration(self.name, self.email, self.timestamp, self.timeslots)

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            _normalise(data["name"]),
            _normalise(data["email"]),
            datetime.strptime(data["timestamp"], '%d/%m/%Y %H:%M:%S'),
            [timeslot.replace(' ', '') for timeslot in data["timeslots"].split(',')]
        )


# @dataclass(frozen=True)
# class FullEntry:
#     timestamp: datetime.datetime = field(compare=False)
#     email: str
#     research_consent: str
#     full_name: str
#     first_time_visiting: str
#     referral: str
#     time_in_ttown: str



@dataclass(frozen=True)
class ProtoTimeslot:
    name: str
    slots: int = 0
    unlimited: bool = False

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            data["name"],
            int(data["slots"]),
            data["unlimited"].lower() == "true"
        )

class Timeslot:
    spots: List[Person]
    downprioritised: Set[Person]  # The people who are not allowed to attend this timeslot

    def __init__(self, downprioritised: Optional[Set[Person]] = None):
        self.spots = []
        self.downprioritised = downprioritised or set()

    @property
    def spots_taken(self):
        return len(self.spots)

    def __str__(self):
        content = ', '.join(f"{k}: {str(v)}" for k, v in self.__dict__.items())
        return f"Timeslot({content})"

    def __repr__(self):
        content = ', '.join(f"{k}: {str(v)}" for k, v in self.__dict__.items())
        return f"Timeslot({content})"

    def admit(self, person: Person) -> bool:
        if person in self.downprioritised:
            return False
        self.spots.append(person)
        return True

    def remove(self, person: Person) -> bool:
        try:
            self.spots.remove(person)
            return True
        except ValueError:
            return False


class LimitedTimeslot(Timeslot):
    capacity: int
    waiting_list: List[Person]

    def __init__(self, capacity: int):
        super().__init__()
        self.capacity = capacity
        self.waiting_list = []

    @property
    def spots_available(self):
        return self.capacity - self.spots_taken

    def admit(self, person: Person) -> bool:
        if person in self.downprioritised:
            self.waiting_list.append(person)
            return False
        if self.spots_available > 0:
            self.spots.append(person)
            return True
        self.waiting_list.insert(0, person)
        return False




if __name__ == '__main__':
    a = Person("Halvor Bakken Smedås", "halvor@restore-trd.no")
    b = Person("Halvor Bakken Smedaas", "halvor@restore-trd.no")
    # others = [
    #     Person("Halvor Bakken Smedås", "halvor@restore-trd.no"),
    #     Person("Klara Schlüter", "halvor@restore-trd.no"),
    #     Person("Bakken Smedås", "halvor@restore-trd.no"),
    #     Person("Halvor Smedås", "halvor@restore-trd.no"),
    #     Person("Halvor Smedås", "halvor@restore-trd.n"),
    # ]
    #
    # for b in others:
    #     if not a == b:
    #         print("Not the same:", a, b)
    #     if not a.similar(b):
    #         print("Not similar:", a, b)
