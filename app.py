import math
import random
import re
import unicodedata

import requests
import streamlit as st

API_URL = "https://api.football-data.org/v4"

COMPETITIONS = {
    "Ligue 1": "FL1",
    "Premier League": "PL",
    "La Liga": "PD",
    "Serie A": "SA",
    "Bundesliga": "BL1",
    "Ligue des champions": "CL",
}

MAX_GOALS = 10

GENERIC = {
    "fc", "ac", "as", "aj", "cf", "sc", "rc", "us", "ssc", "ss", "afc",
    "sv", "fsv", "vfl", "vfb", "fk", "ud", "cd", "rcd", "ca", "og", "de", "1",
}

ALIASES = {
    "psg": "paris saint germain",
    "om": "marseille",
    "ol": "lyonnais",
    "real": "real madrid",
    "barca": "barcelona",
    "barcelone": "barcelona",
    "bayern": "bayern",
    "city": "manchester city",
    "man city": "manchester city",
    "united": "manchester united",
    "man utd": "manchester united",
    "spurs": "tottenham",
    "atletico": "atletico",
    "inter": "internazionale",
    "juve": "juventus",
    "milan": "ac milan",
}

HELP = (
    "Je n'ai pas trouvé deux équipes dans ton message. 🤔\n\n"
    "Écris par exemple :\n"
    "- `PSG - Real Madrid`\n"
    "- `Auxerre contre Monaco`\n"
    "- `Arsenal vs Chelsea`\n\n"
    "La première équipe écrite joue à domicile. "
    "Les deux équipes doivent jouer dans la même compétition "
    "(ou en Ligue des champions)."
)

# ---------- CONVERSATION ----------
PROBLEM = [
    "marche pas", "pas marche", "ne marche pas", "fonctionne pas",
    "erreur", "bug", "probleme", "bloque", "faux", "mauvais", "pas bon",
]
THANKS = ["merci", "thanks", "thank you"]
PRAISE = [
    "bravo", "felicitations", "felicitation", "bien joue", "bien fait",
    "super", "genial", "excellent", "top", "parfait", "chapeau", "cool",
    "impressionnant", "bon travail",
]
GREET = ["salut", "bonjour", "bonsoir", "coucou", "hello", "hey", "yo", "wesh", "slt", "cc", "hi"]
HOW = ["ca va", "comment vas tu", "comment tu vas", "comment allez vous", "tu vas bien"]
BYE = ["au revoir", "bye", "a plus", "a plus tard", "ciao", "a demain", "bonne nuit", "bonne soiree"]
WHO = [
    "qui es tu", "t es qui", "tu es qui", "ton nom", "tu t appelles",
    "tu fais quoi", "tu sais faire", "aide", "aide moi", "help",
    "comment ca marche", "comment utiliser",
]


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def has_any(text: str, phrases) -> bool:
    padded = f" {norm(text)} "
    return any(f" {p} " in padded for p in phrases)


def looks_like_match(text: str) -> bool:
    low = text.lower()
    if "-" in low or "–" in low:
        return True
    padded = f" {norm(text)} "
    return any(f" {w} " in padded for w in ("vs", "versus", "contre", "face a"))


def small_talk(text: str):
    """Répond aux messages de conversation. Retourne None si rien ne correspond."""
    if has_any(text, PROBLEM):
        return random.choice([
            "Oh, désolé que ça n'ait pas marché ! 😅 Écris les deux équipes comme ceci : "
            "`PSG - Real Madrid`. Vérifie l'orthographe, et change de compétition en haut "
            "si besoin. Réessaie, je suis là ! 💪",
            "Aïe, pardon pour ça ! 🙏 Essaie avec ce format : `Auxerre - Monaco`. "
            "La première équipe joue à domicile. Dis-moi si ça passe maintenant !",
        ])
    if has_any(text, THANKS):
        return random.choice([
            "Avec plaisir ! 😊 Envoie-moi un autre match quand tu veux. ⚽",
            "De rien ! 🙌 Un autre match à analyser ?",
        ])
    if has_any(text, PRAISE):
        return random.choice([
            "Merci beaucoup, ça me fait plaisir ! 🙏🔥 Envoie-moi un autre match, "
            "je suis chaud ! ⚽",
            "Merci champion ! 😎 Le travail continue : donne-moi un match à analyser.",
        ])
    greet = has_any(text, GREET)
    how = has_any(text, HOW)
    if greet or how:
        start = "Salut ! 👋 " if greet else ""
        mid = "Je vais très bien, merci ! ⚽ " if how else ""
        return start + mid + "Écris-moi un match, par exemple `PSG - Real Madrid`."
    if has_any(text, BYE):
        return random.choice([
            "À bientôt ! 👋 Reviens quand tu veux pour une autre prédiction. ⚽",
            "Au revoir ! 😊 Bons matchs !",
        ])
    if has_any(text, WHO):
        return (
            "Je suis le bot de prédictions de **Denis Paco Digital** ⚽. "
            "J'analyse les buts marqués et encaissés des équipes pour calculer "
            "le score probable et les chances de victoire.\n\n"
            "Écris par exemple : `PSG - Real Madrid`."
        )
    return None


# ---------- OUTILS DE TEXTE ----------
def strip_generic(n: str) -> str:
    return " ".join(w for w in n.split() if w not in GENERIC)


def team_keys(name: str, short: str):
    n = norm(name)
    s = norm(short)
    keys = {n, s, strip_generic(n), strip_generic(s)}
    for alias, target in ALIASES.items():
        if target in n:
            keys.add(alias)
    keys.discard("")
    return keys


def find_teams(text: str, model):
    """Trouve les équipes citées dans le message, dans l'ordre d'apparition."""
    padded = f" {norm(text)} "
    candidates = []
    for team, keys in model["keys"].items():
        for k in keys:
            idx = padded.find(f" {k} ")
            if idx != -1:
                candidates.append((len(k), idx + 1, team))

    candidates.sort(reverse=True)
    accepted = []
    used_teams = set()
    for length, start, team in candidates:
        end = start + length
        if team in used_teams:
            continue
        if any(start < e and s < end for _, s, e in accepted):
            continue
        accepted.append((team, start, end))
        used_teams.add(team)

    accepted.sort(key=lambda x: x[1])
    return [t for t, _, _ in accepted]


# ---------- DONNÉES ----------
@st.cache_data(ttl=3600, show_spinner=False)
def get_matches(code: str):
    """Récupère les matchs terminés de la saison en cours."""
    headers = {"X-Auth-Token": st.secrets["FOOTBALL_API_KEY"]}
    r = requests.get(
        f"{API_URL}/competitions/{code}/matches",
        headers=headers,
        params={"status": "FINISHED"},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()["matches"]


def build_model(matches):
    """Calcule la force d'attaque et de défense de chaque équipe."""
    teams = {}
    home_goals_total = away_goals_total = games = 0

    for m in matches:
        ft = m["score"]["fullTime"]
        hg, ag = ft["home"], ft["away"]
        if hg is None or ag is None:
            continue
        h, a = m["homeTeam"]["name"], m["awayTeam"]["name"]
        hs = m["homeTeam"].get("shortName") or h
        as_ = m["awayTeam"].get("shortName") or a
        teams.setdefault(h, {"gf": 0, "ga": 0, "n": 0, "short": hs})
        teams.setdefault(a, {"gf": 0, "ga": 0, "n": 0, "short": as_})
        teams[h]["gf"] += hg
        teams[h]["ga"] += ag
        teams[h]["n"] += 1
        teams[a]["gf"] += ag
        teams[a]["ga"] += hg
        teams[a]["n"] += 1
        home_goals_total += hg
        away_goals_total += ag
        games += 1

    if games == 0:
        return None

    avg_home = home_goals_total / games
    avg_away = away_goals_total / games
    avg_team = (avg_home + avg_away) / 2

    strengths = {}
    keys = {}
    for t, s in teams.items():
        strengths[t] = {
            "attack": (s["gf"] / s["n"]) / avg_team,
            "defense": (s["ga"] / s["n"]) / avg_team,
        }
        keys[t] = team_keys(t, s["short"])
    return {
        "strengths": strengths,
        "avg_home": avg_home,
        "avg_away": avg_away,
        "keys": keys,
    }


def poisson(k: int, lam: float) -> float:
    return math.exp(-lam) * lam**k / math.factorial(k)


def predict(model, home: str, away: str):
    s = model["strengths"]
    lam_home = s[home]["attack"] * s[away]["defense"] * model["avg_home"]
    lam_away = s[away]["attack"] * s[home]["defense"] * model["avg_away"]

    win_home = draw = win_away = over25 = btts = 0.0
    best_score, best_prob = (0, 0), 0.0

    for i in range(MAX_GOALS + 1):
        for j in range(MAX_GOALS + 1):
            p = poisson(i, lam_home) * poisson(j, lam_away)
            if i > j:
                win_home += p
            elif i == j:
                draw += p
            else:
                win_away += p
            if i + j > 2:
                over25 += p
            if i > 0 and j > 0:
                btts += p
            if p > best_prob:
                best_prob, best_score = p, (i, j)

    total = win_home + draw + win_away
    return {
        "lam_home": lam_home,
        "lam_away": lam_away,
        "win_home": win_home / total,
        "draw": draw / total,
        "win_away": win_away / total,
        "over25": over25 / total,
        "btts": btts / total,
        "score": best_score,
    }


def recent_form(matches, team: str, n: int = 5):
    """Retourne les n derniers résultats sous forme V / N / D."""
    played = [
        m for m in matches
        if team in (m["homeTeam"]["name"], m["awayTeam"]["name"])
        and m["score"]["fullTime"]["home"] is not None
    ]
    played.sort(key=lambda m: m["utcDate"])
    form = []
    for m in played[-n:]:
        hg = m["score"]["fullTime"]["home"]
        ag = m["score"]["fullTime"]["away"]
        is_home = m["homeTeam"]["name"] == team
        gf, ga = (hg, ag) if is_home else (ag, hg)
        form.append("V" if gf > ga else "N" if gf == ga else "D")
    return " ".join(form) if form else "—"


# ---------- CHAT ----------
def format_reply(home, away, r, matches, comp):
    return (
        f"**{home} vs {away}** ({comp})\n\n"
        f"🎯 Score le plus probable : **{r['score'][0]} - {r['score'][1]}**\n\n"
        f"- Victoire {home} : **{r['win_home']:.0%}**\n"
        f"- Match nul : **{r['draw']:.0%}**\n"
        f"- Victoire {away} : **{r['win_away']:.0%}**\n\n"
        f"- Plus de 2,5 buts : **{r['over25']:.0%}**\n"
        f"- Les 2 équipes marquent : **{r['btts']:.0%}**\n\n"
        f"Buts attendus : {home} {r['lam_home']:.2f} — {away} {r['lam_away']:.2f}\n\n"
        f"Forme de {home} : {recent_form(matches, home)}\n\n"
        f"Forme de {away} : {recent_form(matches, away)}\n\n"
        "_Probabilités statistiques, pas des certitudes._"
    )


def answer_chat(text: str, selected: str) -> str:
    # 1) Conversation simple (salut, merci, bravo...)
    if not looks_like_match(text):
        reply = small_talk(text)
        if reply:
            return reply

    # 2) Prédiction de match
    order = []
    for c in [selected, "Ligue des champions", *COMPETITIONS]:
        if c not in order:
            order.append(c)

    errors = 0
    for comp in order:
        try:
            matches = get_matches(COMPETITIONS[comp])
            model = build_model(matches)
        except Exception:
            errors += 1
            continue
        if model is None:
            continue
        teams = find_teams(text, model)
        if len(teams) >= 2:
            home, away = teams[0], teams[1]
            r = predict(model, home, away)
            return format_reply(home, away, r, matches, comp)

    if errors == len(order):
        return "Impossible de récupérer les données pour le moment. Réessaie dans une minute."
    return HELP


# ---------- INTERFACE ----------
st.set_page_config(page_title="Prédictions Foot", page_icon="⚽", layout="centered")

st.title("⚽ Prédictions de matchs")
st.caption("Denis Paco Digital — analyse statistique des matchs de football")

competition = st.selectbox("Compétition", list(COMPETITIONS.keys()))

try:
    with st.spinner("Chargement des données..."):
        matches = get_matches(COMPETITIONS[competition])
        model = build_model(matches)
except Exception as e:
    st.error(
        "Impossible de récupérer les données. Vérifie ta clé API "
        f"(FOOTBALL_API_KEY). Détail : {e}"
    )
    st.stop()

if model is None:
    st.warning("Pas encore assez de matchs joués pour cette compétition.")
    st.stop()

team_names = sorted(model["strengths"].keys())

col1, col2 = st.columns(2)
home = col1.selectbox("🏠 Équipe à domicile", team_names, index=0)
away = col2.selectbox("✈️ Équipe à l'extérieur", team_names, index=min(1, len(team_names) - 1))

if st.button("Prédire le match", type="primary", use_container_width=True):
    if home == away:
        st.warning("Choisis deux équipes différentes.")
    else:
        r = predict(model, home, away)

        st.subheader(f"{home} vs {away}")
        st.metric("Score le plus probable", f"{r['score'][0]} - {r['score'][1]}")

        c1, c2, c3 = st.columns(3)
        c1.metric(f"Victoire {home}", f"{r['win_home']:.0%}")
        c2.metric("Match nul", f"{r['draw']:.0%}")
        c3.metric(f"Victoire {away}", f"{r['win_away']:.0%}")

        st.progress(r["win_home"], text=f"{home} : {r['win_home']:.0%}")
        st.progress(r["draw"], text=f"Nul : {r['draw']:.0%}")
        st.progress(r["win_away"], text=f"{away} : {r['win_away']:.0%}")

        c4, c5 = st.columns(2)
        c4.metric("Plus de 2,5 buts", f"{r['over25']:.0%}")
        c5.metric("Les 2 équipes marquent", f"{r['btts']:.0%}")

        st.write(
            f"**Buts attendus** : {home} {r['lam_home']:.2f} — "
            f"{away} {r['lam_away']:.2f}"
        )
        st.write(f"**Forme de {home}** (5 derniers) : {recent_form(matches, home)}")
        st.write(f"**Forme de {away}** (5 derniers) : {recent_form(matches, away)}")

st.divider()
st.subheader("💬 Discute avec le bot")
st.caption("Dis salut, ou écris un match : PSG - Real Madrid, Auxerre contre Monaco...")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "Salut ! 👋 Je suis le bot de prédictions de Denis Paco Digital. "
                "Écris-moi un match et je te donne ma prédiction. "
                "Exemple : `PSG - Real Madrid`"
            ),
        }
    ]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

prompt = st.chat_input("Écris un message ou un match, ex : PSG - Real Madrid")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Je réfléchis..."):
            reply = answer_chat(prompt, competition)
        st.markdown(reply)
    st.session_state.messages.append({"role": "assistant", "content": reply})

st.divider()
st.caption(
    "⚠️ Ces prédictions sont des probabilités statistiques, pas des certitudes. "
    "Elles ne tiennent pas compte des blessures ni des suspensions. "
    "Ne mise jamais d'argent que tu ne peux pas te permettre de perdre."
)
