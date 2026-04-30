import anthropic
import requests
import time
import os
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic()
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
TMDB_BASE = "https://api.themoviedb.org/3"

def claude_request(prompt, max_tokens=800):
    for attempt in range(3):
        try:
            return client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}]
            ).content[0].text.strip()
        except anthropic.APIStatusError as e:
            if e.status_code == 529 and attempt < 2:
                wait = (attempt + 1) * 10
                print(f"API overloaded, retrying in {wait} seconds...")
                time.sleep(wait)
            else:
                raise


def search_director(name):
    response = requests.get(f"{TMDB_BASE}/search/person", params={
        "api_key": TMDB_API_KEY,
        "query": name
    })
    results = response.json().get('results', [])
    if not results:
        print(f"Director '{name}' not found on TMDB.")
        return None
    return results[0]


def get_filmography(director_id):
    response = requests.get(f"{TMDB_BASE}/person/{director_id}/movie_credits", params={
        "api_key": TMDB_API_KEY
    })
    credits = response.json().get('crew', [])

    films = [
        c for c in credits
        if c['job'] == 'Director' and c.get('vote_count', 0) > 100
    ]

    films.sort(key=lambda x: x.get('vote_average', 0), reverse=True)

    return films[:15]


def director_deep_dive(director_name):
    print(f"\nSearching TMDB for {director_name}...\n")

    director = search_director(director_name)
    if not director:
        return

    director_id = director['id']
    confirmed_name = director['name']
    print(f"Found: {confirmed_name}\n")

    films = get_filmography(director_id)
    if not films:
        print("No films found.")
        return

    filmography_text = "\n".join([
        f"- {f['title']} ({f.get('release_date', 'N/A')[:4]}) -- TMDB rating: {f.get('vote_average', 'N/A')}/10 ({f.get('vote_count', 0)} votes)"
        for f in films
    ])

    print("Analyzing with Claude...\n")

    filmography_prompt = f"""You are a film expert. Here is the verified TMDB filmography for director {confirmed_name}, sorted by rating:

{filmography_text}

Based on this data, rank their top 10 films. For each include:
- Rank
- Title and year
- TMDB rating
- One sentence on why it ranks here

Use only the films listed above."""

    filmography = claude_request(filmography_prompt)

    themes_prompt = f"""You are a film critic. Based on this filmography for {confirmed_name}:

{filmography_text}

Analyze:
- 3-4 recurring themes across their work
- Their signature visual style and techniques
- How their style has evolved over their career

Reference specific films from the list in your analysis."""

    themes = claude_request(themes_prompt)

    divider = "=" * 50

    print(divider)
    print(f"  DIRECTOR DEEP DIVE: {confirmed_name.upper()}")
    print(divider)

    print("\n-- FILMOGRAPHY (RANKED) ---------------------------\n")
    print(filmography)

    print("\n-- RECURRING THEMES & STYLE -----------------------\n")
    print(themes)

    print(f"\n{divider}\n")


if __name__ == '__main__':
    director = input("Enter a director's name: ")
    director_deep_dive(director)