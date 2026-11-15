import json

# 32 Resident names
RESIDENT_NAMES = {
    1: "Prabakar",
    2: "Ramesh",
    3: "Suresh",
    4: "Venkatesh",
    5: "Lakshmi",
    6: "Srinivas",
    7: "Anjaneyulu",
    8: "Nagaraju",
    9: "Satyanarayana",
    10: "Appa Rao",
    11: "Mallikarjun",
    12: "Koteswara Rao",
    13: "K. Venkatesh",
    14: "Subba Rao",
    15: "Ramakrishna",
    16: "Narayana Murthy",
    17: "Govinda Rajulu",
    18: "Chandra Sekhar",
    19: "Venkata Ramana",
    20: "Samba Siva Rao",
    21: "Balaraju",
    22: "Thirupathi Rao",
    23: "Jagadeesh",
    24: "Mohan Rao",
    25: "Siva Kumar",
    26: "Ranga Rao",
    27: "Bhaskara Rao",
    28: "Prasad Babu",
    29: "Vijay Kumar",
    30: "Radha Krishna",
    31: "Visweswara Rao",
    32: "Murali Krishna"
}

with open("house_accounts.json", "r", encoding="utf-8") as f:
    accounts = json.load(f)

for acc in accounts:
    num = acc["houseNumber"]
    name = RESIDENT_NAMES.get(num, f"Resident {num}")
    primary_username = f"House {num} {name}"
    
    # Aliases
    aliases = [
        primary_username.lower(),
        f"house {num}".lower(),
        f"house{num}".lower(),
        f"house-{num}".lower(),
        f"h{num}".lower(),
        name.lower(),
        acc["email"].lower()
    ]
    for em in acc.get("aliasEmails", []):
        aliases.append(em.lower())
    if num == 13:
        aliases.extend(["house 13", "house13"])
    elif num == 1:
        aliases.extend(["prabakar", "house 1 prabakar"])

    acc["username"] = primary_username
    acc["residentName"] = name
    acc["aliasUsernames"] = list(dict.fromkeys(aliases))
    acc["loginDisplay"] = f"Username: {primary_username} · Pass: 1111"

with open("house_accounts.json", "w", encoding="utf-8") as f:
    json.dump(accounts, f, indent=2, ensure_ascii=False)

print(f"Updated {len(accounts)} accounts in house_accounts.json successfully.")
print("House 1 username:", accounts[0]["username"])
print("House 13 username:", accounts[12]["username"])
