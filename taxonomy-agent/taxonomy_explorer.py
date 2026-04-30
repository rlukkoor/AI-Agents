#!/usr/bin/env python3
"""
Taxonomy Explorer CLI
---------------------
Classify any organism by genus, species (scientific or common name).
Powered by Claude AI + Brave Search for accuracy.

Requirements:
    pip install anthropic requests

Environment variables:
    ANTHROPIC_API_KEY  - Your Anthropic API key
    BRAVE_API_KEY      - Your Brave Search API key
"""

import os
import sys
import json
import textwrap
import requests
import anthropic
from dotenv import load_dotenv

# ── Config ────────────────────────────────────────────────────────────────────

load_dotenv()
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
BRAVE_API_KEY     = os.environ.get("BRAVE_API_KEY")
MODEL             = "claude-sonnet-4-20250514"
MAX_TOKENS        = 2500
DAGGER            = "\u2020"
WIDTH             = 65

# ── System prompts ────────────────────────────────────────────────────────────

CLASSIFY_PROMPT = """You are a precise taxonomy expert covering ALL life — both living and extinct.
The user will provide a query along with web search results to help ensure accuracy.
Use the search results to verify and supplement your knowledge.

The user may provide:
  - A genus name        (e.g. "Ursus", "Tyrannosaurus")
  - A species name      (e.g. "Panthera leo", "Ursus maritimus")
  - A common name       (e.g. "killer whale", "polar bear", "T. rex")

First determine the inputType ("genus" or "species"), resolving common names to their
correct scientific name before classifying.

RULES:

1. GENUS input:
   - Full taxonomic hierarchy Domain to Genus.
   - Include ALL ranks that apply: Domain, Kingdom, Phylum, Subphylum, Superclass,
     Class, Subclass, Infraclass, Clade (where used), Superorder, Order, Suborder,
     Infraorder, Parvorder, Superfamily, Family, Subfamily, Tribe, Subtribe, Genus.
     Include Clade rows for well-known clades (e.g. Dinosauria, Tetrapoda).
   - Only include ranks that genuinely apply; do not invent ranks.
   - List ALL known species (living + extinct).
   - Each taxonomy row and each species has an "extinct" boolean.
     Set extinct:true for a rank only if the ENTIRE group is extinct.
   - Schema:
   {
     "inputType": "genus",
     "resolvedFrom": "common name used, or null if already scientific",
     "genusExtinct": true_or_false,
     "taxonomy": [
       { "rank": "Domain",  "name": "...", "extinct": false },
       { "rank": "Genus",   "name": "...", "extinct": true_or_false }
     ],
     "species": [
       { "scientific": "...", "common": "...", "extinct": true_or_false }
     ]
   }

2. SPECIES input:
   - Full taxonomic hierarchy Domain to Species (same rank list as above, plus Species).
   - Each taxonomy row has an "extinct" boolean (same rule as above).
   - 3 to 5 notable points.
   - Schema:
   {
     "inputType": "species",
     "resolvedFrom": "common name used, or null if already scientific",
     "commonName": "...",
     "scientificName": "...",
     "author": "...",
     "extinct": true_or_false,
     "taxonomy": [
       { "rank": "Domain",  "name": "...", "extinct": false },
       { "rank": "Species", "name": "...", "extinct": true_or_false }
     ],
     "notablePoints": ["...", "...", "..."]
   }

3. Unrecognized input:
   { "inputType": "error", "message": "..." }

IMPORTANT: Return raw JSON only. No backticks, no markdown, no explanation."""

ETYMOLOGY_PROMPT = """You are a classical languages expert specialising in biological nomenclature.
Given a scientific name (genus, species epithet, or both), explain the etymology of each part:
its language of origin (Latin, Greek, person name, place name, etc.), literal meaning,
and why it was chosen for this organism if known.

Return JSON only. No backticks, no markdown.
Schema:
{
  "terms": [
    {
      "term": "...",
      "language": "...",
      "literal": "...",
      "reason": "..."
    }
  ]
}"""

TREE_PROMPT = """You are a taxonomy and phylogenetics expert.
Given a genus and its species list, produce a simple ASCII cladogram showing the
approximate phylogenetic relationships between the species based on current understanding.
Use standard ASCII tree characters: | \\ / and dashes.

Return JSON only. No backticks, no markdown.
Schema:
{
  "tree": "<multi-line ASCII string>",
  "notes": "brief note on the basis for this grouping (e.g. morphological, molecular)"
}"""

# ── Session state ─────────────────────────────────────────────────────────────

session = {
    "last_result": None,
    "last_genus":  None,
}

# ── Brave Search ──────────────────────────────────────────────────────────────

def brave_search(query, count=5):
    if not BRAVE_API_KEY:
        return "(Brave search unavailable — BRAVE_API_KEY not set)"
    try:
        resp = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": BRAVE_API_KEY,
            },
            params={"q": query, "count": count},
            timeout=8,
        )
        resp.raise_for_status()
        results = resp.json().get("web", {}).get("results", [])
        if not results:
            return "(No search results found)"
        return "\n".join(
            "- {}: {} ({})".format(r.get("title",""), r.get("description",""), r.get("url",""))
            for r in results
        )
    except Exception as e:
        return "(Search error: {})".format(e)

# ── Claude helpers ────────────────────────────────────────────────────────────

def call_claude(system, user, max_tokens=MAX_TOKENS):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    resp = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    raw   = resp.content[0].text.strip()
    clean = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(clean)

def classify(user_input):
    search_results = brave_search("{} taxonomy classification scientific".format(user_input))
    user_msg = "Input: {}\n\nWeb search results for context:\n{}".format(user_input, search_results)
    return call_claude(CLASSIFY_PROMPT, user_msg)

def get_etymology(scientific_name):
    return call_claude(ETYMOLOGY_PROMPT, "Scientific name: {}".format(scientific_name), max_tokens=1000)

def get_tree(genus_name, species):
    species_list = "\n".join(
        "  {} {}  ({})".format(DAGGER if s.get("extinct") else " ", s["scientific"], s.get("common",""))
        for s in species
    )
    return call_claude(TREE_PROMPT, "Genus: {}\n\nSpecies:\n{}".format(genus_name, species_list), max_tokens=1000)

# ── Display helpers ───────────────────────────────────────────────────────────

def sep(char="-", width=WIDTH):
    return char * width

def wrap_print(text, indent="  "):
    for line in textwrap.wrap(text, width=WIDTH - len(indent)):
        print(indent + line)

def print_taxonomy_table(taxonomy):
    col = max(len(r["rank"]) for r in taxonomy)
    for row in taxonomy:
        prefix = DAGGER if row.get("extinct") else " "
        print("  {:<{}}  {}{}".format(row["rank"], col, prefix, row["name"]))

def display_genus(data):
    genus_name   = next((r["name"] for r in data["taxonomy"] if r["rank"] == "Genus"), "Unknown")
    extinct_note = "  {} EXTINCT".format(DAGGER) if data.get("genusExtinct") else ""
    resolved     = data.get("resolvedFrom")

    print()
    print(sep("="))
    print("  GENUS: {}{}".format(genus_name, extinct_note))
    if resolved:
        print("  (resolved from: {})".format(resolved))
    print(sep("="))
    print()
    print_taxonomy_table(data["taxonomy"])

    species = data.get("species", [])
    if species:
        living  = [s for s in species if not s.get("extinct")]
        extinct = [s for s in species if s.get("extinct")]
        print()
        print(sep())
        print("  KNOWN SPECIES  ({} total — {} extant, {} extinct)".format(
            len(species), len(living), len(extinct)))
        print(sep())
        for sp in species:
            tag = " {}".format(DAGGER) if sp.get("extinct") else "  "
            print("{} {:<42} {}".format(tag, sp["scientific"], sp.get("common", "")))

    print()
    print("  Commands available for this result:")
    print("    tree        ASCII clade tree of these species")
    print("    etymology   Etymology of the genus name")
    print()

def display_species(data):
    sci_name     = data.get("scientificName", "Unknown")
    common       = data.get("commonName", "")
    author       = data.get("author", "")
    extinct_note = "  {} EXTINCT".format(DAGGER) if data.get("extinct") else ""
    author_note  = "  ({})".format(author) if author else ""
    resolved     = data.get("resolvedFrom")

    print()
    print(sep("="))
    print("  SPECIES: {}{}{}".format(sci_name, author_note, extinct_note))
    if common:
        print("  Common name: {}".format(common))
    if resolved:
        print("  (resolved from: {})".format(resolved))
    print(sep("="))
    print()
    print_taxonomy_table(data["taxonomy"])

    points = data.get("notablePoints", [])
    if points:
        print()
        print(sep())
        print("  NOTABLE POINTS")
        print(sep())
        for i, pt in enumerate(points, 1):
            lines = textwrap.wrap(pt, width=WIDTH - 6)
            for j, line in enumerate(lines):
                if j == 0:
                    print("  {}. {}".format(i, line))
                else:
                    print("     {}".format(line))

    print()
    print("  Commands available for this result:")
    print("    up          Classify the parent genus")
    print("    siblings    List all species in the same genus")
    print("    etymology   Etymology of the scientific name")
    print()

def display_result(data):
    if data["inputType"] == "genus":
        display_genus(data)
    elif data["inputType"] == "species":
        display_species(data)
    else:
        print("\n  Error: {}\n".format(data.get("message", "Unknown error")))

# ── Feature commands ──────────────────────────────────────────────────────────

def cmd_up():
    last = session["last_result"]
    if not last or last["inputType"] != "species":
        print("\n  'up' requires a species result. Look up a species first.\n")
        return
    genus = session["last_genus"]
    if not genus:
        print("\n  Could not determine parent genus.\n")
        return
    print("\n  Traversing up to genus '{}'... ".format(genus), end="", flush=True)
    try:
        result = classify(genus)
        print("done.")
        _store_result(result)
        display_result(result)
    except Exception as e:
        print("\n  Error: {}\n".format(e))

def cmd_siblings():
    last = session["last_result"]
    if not last or last["inputType"] != "species":
        print("\n  'siblings' requires a species result. Look up a species first.\n")
        return
    genus = session["last_genus"]
    if not genus:
        print("\n  Could not determine parent genus.\n")
        return
    print("\n  Fetching all species in genus '{}'... ".format(genus), end="", flush=True)
    try:
        result = classify(genus)
        print("done.")
        _store_result(result)
        species = result.get("species", [])
        if not species:
            print("  No species found.\n")
            return
        living  = [s for s in species if not s.get("extinct")]
        extinct = [s for s in species if s.get("extinct")]
        print()
        print(sep())
        print("  SPECIES IN {}  ({} total — {} extant, {} extinct)".format(
            genus.upper(), len(species), len(living), len(extinct)))
        print(sep())
        for sp in species:
            tag = " {}".format(DAGGER) if sp.get("extinct") else "  "
            print("{} {:<42} {}".format(tag, sp["scientific"], sp.get("common", "")))
        print()
    except Exception as e:
        print("\n  Error: {}\n".format(e))

def cmd_tree():
    last = session["last_result"]
    if not last or last["inputType"] != "genus":
        print("\n  'tree' requires a genus result. Look up a genus first.\n")
        return
    genus   = next((r["name"] for r in last["taxonomy"] if r["rank"] == "Genus"), None)
    species = last.get("species", [])
    if not genus or not species:
        print("\n  Not enough data to draw a tree.\n")
        return
    print("\n  Building clade tree for {}... ".format(genus), end="", flush=True)
    try:
        result = get_tree(genus, species)
        print("done.")
        print()
        print(sep())
        print("  CLADE TREE — {}".format(genus))
        print(sep())
        for line in result.get("tree", "").splitlines():
            print("  " + line)
        notes = result.get("notes", "")
        if notes:
            print()
            wrap_print("Note: {}".format(notes))
        print()
    except Exception as e:
        print("\n  Error: {}\n".format(e))

def cmd_etymology():
    last = session["last_result"]
    if not last or last["inputType"] not in ("genus", "species"):
        print("\n  'etymology' requires a classify result first.\n")
        return
    if last["inputType"] == "genus":
        sci = next((r["name"] for r in last["taxonomy"] if r["rank"] == "Genus"), None)
    else:
        sci = last.get("scientificName")
    if not sci:
        print("\n  Could not determine scientific name.\n")
        return
    print("\n  Looking up etymology for '{}'... ".format(sci), end="", flush=True)
    try:
        result = get_etymology(sci)
        print("done.")
        print()
        print(sep())
        print("  ETYMOLOGY — {}".format(sci))
        print(sep())
        for term in result.get("terms", []):
            print("\n  {}  [{}]".format(term.get("term",""), term.get("language","")))
            print("    Literal:  {}".format(term.get("literal","")))
            wrap_print("Reason:   {}".format(term.get("reason","")), indent="    ")
        print()
    except Exception as e:
        print("\n  Error: {}\n".format(e))

def cmd_help():
    print()
    print(sep("="))
    print("  COMMANDS")
    print(sep("="))
    print("  <name>      Classify a genus, species (scientific or common name)")
    print("                e.g.  Ursus")
    print("                e.g.  Panthera leo")
    print("                e.g.  killer whale")
    print("                e.g.  Otodus megalodon")
    print()
    print("  NAVIGATION  (after a result)")
    print("  up          After a species — classify its parent genus")
    print("  siblings    After a species — list all species in that genus")
    print("  tree        After a genus   — show an ASCII clade tree")
    print("  etymology   After any result — explain the scientific name(s)")
    print()
    print("  OTHER")
    print("  help        Show this help")
    print("  quit        Exit  (also: exit, q, Ctrl+C)")
    print(sep("="))
    print()

# ── State helpers ─────────────────────────────────────────────────────────────

def _store_result(data):
    session["last_result"] = data
    if data["inputType"] in ("genus", "species"):
        genus = next((r["name"] for r in data["taxonomy"] if r["rank"] == "Genus"), None)
        session["last_genus"] = genus

# ── Startup check ─────────────────────────────────────────────────────────────

def check_env():
    ok = True
    if not ANTHROPIC_API_KEY:
        print("  Error: ANTHROPIC_API_KEY environment variable is not set.")
        ok = False
    if not BRAVE_API_KEY:
        print("  Warning: BRAVE_API_KEY is not set — web search context will be skipped.")
    return ok

# ── Main loop ─────────────────────────────────────────────────────────────────

def main():
    if not check_env():
        sys.exit(1)

    print()
    print(sep("="))
    print("  TAXONOMY EXPLORER")
    print("  Powered by Claude + Brave Search")
    print(sep("="))
    print("  Classify any organism by genus, species, or common name.")
    print()
    print("  QUICK START")
    print("    killer whale        resolves & classifies Orcinus orca")
    print("    Ursus               full genus listing with all species")
    print("    Otodus megalodon    species with extinct rank markers")
    print()
    print("  NAVIGATION  (type after viewing a result)")
    print("    up          Classify the parent genus of a species result")
    print("    siblings    List all species sharing the same genus")
    print("    tree        ASCII clade tree for a genus result")
    print("    etymology   Explain the Latin/Greek roots of the name")
    print()
    print("  OTHER")
    print("    help        Full command reference")
    print("    quit        Exit  (also: exit, q, Ctrl+C)")
    print(sep("="))

    while True:
        try:
            user_input = input("\n> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\n  Goodbye!")
            break

        if not user_input:
            continue

        cmd = user_input.lower()

        if cmd in {"quit", "exit", "q"}:
            print("\n  Goodbye!")
            break
        elif cmd == "help":
            cmd_help()
        elif cmd == "up":
            cmd_up()
        elif cmd == "siblings":
            cmd_siblings()
        elif cmd == "tree":
            cmd_tree()
        elif cmd == "etymology":
            cmd_etymology()
        else:
            print("\n  Classifying '{}'... ".format(user_input), end="", flush=True)
            try:
                result = classify(user_input)
                print("done.")
                _store_result(result)
                display_result(result)
            except json.JSONDecodeError:
                print("\n  Error: Could not parse the response. Please try again.\n")
            except Exception as e:
                print("\n  Error: {}\n".format(e))

if __name__ == "__main__":
    main()