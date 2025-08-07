
import re


DOMAIN_REGEX = re.compile(
    r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)"
    r"(?:\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*"
    r"\.[A-Za-z]{2,63}$"
)

def classify_lines(lines):
    seen, valid, invalid, dupes = set(), [], [], 0
    from urllib.parse import urlparse
    for l in lines:
        if l in seen:
            dupes += 1
            continue
        seen.add(l)
        # strip scheme and path, keep only the hostname
        parsed = urlparse(l if '://' in l else '//' + l)
        hostname = parsed.netloc or parsed.path
        if DOMAIN_REGEX.match(hostname):
            valid.append(l)
        else:
            invalid.append(l)
    return valid, invalid, dupes