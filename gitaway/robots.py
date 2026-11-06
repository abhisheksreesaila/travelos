"""Read a site's robots.txt before GitAway reads one of its pages for a draft (F-194, D-145).

    check(url)   "" when the page may be read, else a sentence fit to show saying why not

A site that asks Anthropic's or OpenAI's crawlers (`AGENTS`), GitAwayBot, or every robot (`User-agent: *`) to stay away from the page's path is not read: GitAway drafts a trip from
a post only where the site's own file allows an AI tool to. The person is told to paste the text instead. Matching follows RFC 9309: a group is chosen by the product token (the
`*` group when none names us), the longest matching rule wins, an Allow beats a Disallow of the same length, `*` matches any run of characters and a final `$` anchors the end.

A missing or unusable robots.txt (404, 401, 403, any 4xx; a file that is not text) means no restrictions, as the RFC says. One that cannot be fetched right now (a server error, a
timeout, no connection, a redirect loop) does not: the page is left unread and the person is asked to try again, so a hiccup never reads a page its site may have closed to us.
The file is fetched through `safefetch`, so it passes the same guard as any address a person typed.
"""

import re
from urllib.parse import urlsplit

from gitaway import safefetch

AGENTS = ("anthropic-ai", "claudebot", "claude-web", "gptbot", "gitawaybot")      # the product tokens we must not be turned away by, lower case
ASKS_NOT = "This site's robots.txt asks AI tools not to read this page, so GitAway did not draft from it. Paste the text of the post instead."
CANNOT_CHECK = "GitAway could not check this site's robots.txt just now, so it did not read the page. Try again in a minute, or paste the text of the post instead."
TIMEOUT = 4.0


def _groups(text) -> list:
    """[(user-agent tokens, [(allow?, pattern)])] from the file's text."""
    groups, agents, rules, in_rules = [], [], [], False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        field, value = (x.strip() for x in line.split(":", 1))
        field = field.lower()
        if field == "user-agent":
            if in_rules:
                groups.append((agents, rules))
                agents, rules, in_rules = [], [], False
            agents.append(value.lower())
        elif field in ("allow", "disallow"):
            in_rules = True
            rules.append((field == "allow", value))
    if agents:
        groups.append((agents, rules))
    return groups


def _matches(pattern, path) -> bool:
    regex = re.escape(pattern).replace(r"\*", ".*")
    return re.match(regex[:-2] + "$" if regex.endswith(r"\$") else regex, path) is not None


def _allowed(groups, agent, path) -> bool:
    mine = [g for g in groups if agent in g[0]] or [g for g in groups if "*" in g[0]]
    best = None       # (pattern length, allow?) of the longest rule that matches; an Allow wins a tie
    for _agents, rules in mine:
        for allow, pattern in rules:
            if pattern and _matches(pattern, path) and (best is None or (len(pattern), allow) > best):
                best = (len(pattern), allow)
    return best is None or best[1]


def check(url, asked=True) -> str:
    """"" when `url` may be read, else the sentence to show: ASKS_NOT (the site's file says no) or CANNOT_CHECK (the file could not be fetched just now). `asked` is passed on to the fetch
    (whose User-Agent says whether the author asked for this read)."""
    parts = urlsplit(url)
    try:
        got = safefetch.fetch(f"{parts.scheme}://{parts.netloc}/robots.txt", "robots", timeout=TIMEOUT, asked=asked)
    except safefetch.FetchError as e:
        # only a file that may exist but cannot be had right now holds the page back; a 4xx, a file that is not text, a private or unknown address is the page fetch's own business (it says why itself)
        return CANNOT_CHECK if e.code in ("timeout", "network", "redirect", "redirects") or e.code.startswith("http_5") else ""
    groups = _groups(got.text())
    path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
    return "" if all(_allowed(groups, agent, path) for agent in AGENTS) else ASKS_NOT
