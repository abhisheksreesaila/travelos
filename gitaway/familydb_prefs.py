"""The family's own preferences (F-073): one row per setting, for the whole family (not a trip, not a person).

Part of the family database (gitaway.familydb appends PREF_TABLES to its FAMILY_TABLES). Today there is one key, `vegetarian` ("1" or absent), which
makes the Around you tab start on vegetarian food and keep to places that really serve it. The logic is gitaway/around.py.
"""


class FamilyPref:
    key: str
    value: str = ""


PREF_TABLES = [(FamilyPref, "family_prefs", "key")]
