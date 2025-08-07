
import re


DOMAIN_REGEX = re.compile(
    r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)"
    r"(?:\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*"
    r"\.[A-Za-z]{2,63}$"
)

def classify_lines(lines):
    seen, valid, invalid, dupes = set(), [], [], 0
    for l in lines:
        if l in seen:
            dupes += 1; continue
        seen.add(l)
        (valid if DOMAIN_REGEX.match(l) else invalid).append(l)
    return valid, invalid, dupes