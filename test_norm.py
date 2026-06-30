from eightfold.normalize.phone import normalize_phone
from eightfold.normalize.date import normalize_date
from eightfold.normalize.country import normalize_country
from eightfold.normalize.skills import normalize_skill, is_canonical_skill

print("--- phone ---")
for p in ["+91 98765 43210", "9876512345", "+91-99887-66554",
          "+91 90000 11122", "garbage", None, "123"]:
    print(repr(p), "->", normalize_phone(p))

print("--- date ---")
for d in ["2023-03", None, "", "garbage", "2020-6"]:
    print(repr(d), "->", normalize_date(d))

print("--- country ---")
for c in ["India", "USA", "Atlantis", None]:
    print(repr(c), "->", normalize_country(c))

print("--- skills ---")
for s in ["JS", "reactjs", "Python", "Kafka", "System Design"]:
    print(repr(s), "->", normalize_skill(s), "| canonical:", is_canonical_skill(s))