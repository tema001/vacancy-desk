from enum import IntEnum


class Source(IntEnum):
    djinni = 1
    dou = 2


class Status(IntEnum):
    new = 1
    active = 2
    inactive = 3


class EnglishLevel(IntEnum):
    A1 = 1
    A2 = 2
    B1 = 3
    B2 = 4
    C1 = 5
    C2 = 6


class Seniority(IntEnum):
    intern = 1
    junior = 2
    middle = 3
    senior = 4
    lead = 5


class JobFamily(IntEnum):
    backend = 1
    frontend = 2
    mobile = 3
    data = 4
    qa = 5
    devops = 6
    security = 7
    embedded = 8
    product = 9
    delivery = 10
    design = 11
    support = 12
    other = 13


class SkillDepth(IntEnum):
    familiarity = 1
    working = 2
    advanced = 3
    expert = 4


class SkillKind(IntEnum):
    hard = 1
    soft = 2
