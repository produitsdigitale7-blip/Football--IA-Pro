import html
import math
import random
import re
import unicodedata
from datetime import datetime, timedelta, timezone

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
TODAY = [
    "aujourd hui", "ce soir", "demain", "match du jour", "matchs du jour",
    "pronostic du jour", "pronostics du jour",
]
EXPLAIN = [
    "comment tu calcules", "comment tu fais", "comment tu predis",
    "comment ca se calcule", "comment tu as vu", "comment tu as trouve",
    "comment as tu trouve", "pourquoi ce resultat", "explique", "methode",
    "fiable", "tu te bases sur quoi", "sur quoi tu te bases",
]
GREET = ["salut", "bonjour", "bonsoir", "coucou", "hello", "hey", "yo", "wesh", "slt", "cc", "hi"]
HOW = ["ca va", "comment vas tu", "comment tu vas", "comment allez vous", "tu vas bien"]
WELL = ["je vais bien", "ca va bien", "ca va tres bien", "tout va bien", "ca va super", "je vais tres bien"]
ASK_BACK = ["et toi", "et vous", "et tu", "toi meme"]
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
    if has_any(text, TODAY):
        return (
            "Les matchs du jour sont tout en haut de la page 👆. "
            "Appuie sur **« 🔮 Voir la prédiction »** sous le match qui t'intéresse ! "
            "Tu peux aussi m'écrire un match ici, par exemple `PSG - Real Madrid`."
        )
    if has_any(text, EXPLAIN):
        return (
            "Voici comment je fais ⚙️ :\n\n"
            "1. Je récupère les résultats de la saison en cours.\n"
            "2. Je calcule la force d'**attaque** et de **défense** de chaque équipe "
            "(buts marqués et encaissés).\n"
            "3. J'en déduis les buts attendus pour chaque équipe, puis les chances de "
            "victoire, de nul et le score le plus probable.\n\n"
            "Je ne connais pas les blessures ni les suspensions, donc ce sont des "
            "**probabilités**, pas des certitudes. Écris un match pour essayer ! ⚽"
        )

    greet = has_any(text, GREET)
    how = has_any(text, HOW)
    well = has_any(text, WELL)
    back = has_any(text, ASK_BACK)
    if greet or how or well or back:
        parts = []
        if greet:
            parts.append("Salut ! 👋")
        if well:
            parts.append("Content de l'entendre ! 😄")
        if back:
            parts.append(
                "Moi aussi, ça va super, merci ! ⚽" if well
                else "Moi, ça va super, merci ! ⚽"
            )
        elif how and not well:
            parts.append("Ça va super, merci, et toi ? ⚽")
        elif greet and not well:
            parts.append("Ça va ?")
        parts.append("Écris-moi un match, par exemple `PSG - Real Madrid`.")
        return " ".join(parts)

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


# ---------- AFFICHAGE DES LOGOS ----------
def crest_row(home_name, home_crest, away_name, away_crest, middle):
    """Ligne avec les deux logos, les noms des clubs et un texte au milieu."""

    def side(name, crest):
        if crest:
            img = (
                f'<img src="{html.escape(crest, quote=True)}" width="46" height="46" '
                'style="object-fit:contain">'
            )
        else:
            img = '<div style="font-size:34px">⚽</div>'
        return (
            '<div style="flex:1;text-align:center;min-width:0">'
            f'{img}<div style="font-size:0.85em;margin-top:4px">{html.escape(name)}</div>'
            "</div>"
        )

    return (
        '<div style="display:flex;align-items:center;gap:8px;margin:6px 0">'
        + side(home_name, home_crest)
        + f'<div style="text-align:center;font-weight:700;min-width:64px">{middle}</div>'
        + side(away_name, away_crest)
        + "</div>"
    )


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


@st.cache_data(ttl=600, show_spinner=False)
def get_day_matches(day_iso: str):
    """Récupère les matchs d'un jour donné dans les 6 compétitions."""
    headers = {"X-Auth-Token": st.secrets["FOOTBALL_API_KEY"]}
    d0 = datetime.fromisoformat(day_iso).date()
    r = requests.get(
        f"{API_URL}/matches",
        headers=headers,
        params={
            "dateFrom": day_iso,
            "dateTo": (d0 + timedelta(days=1)).isoformat(),
            "competitions": ",".join(COMPETITIONS.values()),
        },
        timeout=20,
    )
    r.raise_for_status()
    return [m for m in r.json().get("matches", []) if m["utcDate"][:10] == day_iso]


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
        teams.setdefault(
            h, {"gf": 0, "ga": 0, "n": 0, "short": hs, "crest": m["homeTeam"].get("crest")}
        )
        teams.setdefault(
            a, {"gf": 0, "ga": 0, "n": 0, "short": as_, "crest": m["awayTeam"].get("crest")}
        )
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
    crests = {}
    for t, s in teams.items():
        strengths[t] = {
            "attack": (s["gf"] / s["n"]) / avg_team,
            "defense": (s["ga"] / s["n"]) / avg_team,
        }
        keys[t] = team_keys(t, s["short"])
        crests[t] = s.get("crest")
    return {
        "strengths": strengths,
        "avg_home": avg_home,
        "avg_away": avg_away,
        "keys": keys,
        "crests": crests,
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


# ---------- AFFICHAGE D'UNE PRÉDICTION ----------
def show_prediction(model, matches, home, away):
    r = predict(model, home, away)

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


# ---------- LISTE DES MATCHS DU JOUR ----------
def render_day_matches(day_matches):
    if not day_matches:
        st.info("Aucun match dans ces compétitions ce jour-là.")
        return

    by_comp = {}
    for m in sorted(day_matches, key=lambda x: x["utcDate"]):
        by_comp.setdefault(m["competition"]["name"], []).append(m)

    for comp_name, items in by_comp.items():
        st.markdown(f"**🏆 {comp_name}**")
        for m in items:
            code = m["competition"].get("code")
            hn = m["homeTeam"].get("name") or "?"
            an = m["awayTeam"].get("name") or "?"
            hc = m["homeTeam"].get("crest")
            ac = m["awayTeam"].get("crest")
            status = m.get("status", "")
            ft = m["score"]["fullTime"]
            hg = ft["home"] if ft["home"] is not None else 0
            ag = ft["away"] if ft["away"] is not None else 0

            if status == "FINISHED":
                middle = f"{hg} - {ag}<br><small>Terminé</small>"
            elif status in ("IN_PLAY", "PAUSED"):
                middle = f"{hg} - {ag}<br><small>🔴 En direct</small>"
            elif status in ("POSTPONED", "SUSPENDED", "CANCELLED"):
                middle = "<small>Reporté</small>"
            else:
                middle = m["utcDate"][11:16]

            with st.container(border=True):
                st.markdown(crest_row(hn, hc, an, ac, middle), unsafe_allow_html=True)

                if status in ("FINISHED", "POSTPONED", "SUSPENDED", "CANCELLED"):
                    continue

                with st.expander("🔮 Voir la prédiction"):
                    try:
                        comp_matches = get_matches(code)
                        comp_model = build_model(comp_matches)
                    except Exception:
                        st.warning("Données indisponibles pour le moment, réessaie dans une minute.")
                        continue
                    if (
                        comp_model is None
                        or hn not in comp_model["strengths"]
                        or an not in comp_model["strengths"]
                    ):
                        st.info("Pas assez de données pour ce match.")
                        continue
                    show_prediction(comp_model, comp_matches, hn, an)


# ---------- CHAT ----------
def format_reply(home, away, r, matches, comp, crests):
    header = crest_row(home, crests.get(home), away, crests.get(away), "VS")
    return (
        f"{header}"
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
    text = text.strip()[:500]

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
            return format_reply(home, away, r, matches, comp, model["crests"])

    if errors == len(order):
        return "Impossible de récupérer les données pour le moment. Réessaie dans une minute."
    return HELP


# ---------- INTERFACE ----------
st.set_page_config(page_title="Prédictions Foot", page_icon="⚽", layout="centered")

st.title("⚽ Prédictions de matchs")
st.caption("Denis Paco Digital — analyse statistique des matchs de football")

# ----- Matchs du jour -----
st.subheader("📅 Les matchs")
day_choice = st.radio(
    "Jour",
    ["Aujourd'hui", "Demain", "Après-demain"],
    horizontal=True,
    label_visibility="collapsed",
)
offset = {"Aujourd'hui": 0, "Demain": 1, "Après-demain": 2}[day_choice]
day = datetime.now(timezone.utc).date() + timedelta(days=offset)
st.caption(f"{day.strftime('%d/%m/%Y')} · heures affichées en UTC (GMT)")

day_matches = None
try:
    with st.spinner("Chargement des matchs..."):
        day_matches = get_day_matches(day.isoformat())
except Exception as e:
    st.warning(f"Impossible de charger les matchs pour le moment. Détail : {e}")

if day_matches is not None:
    render_day_matches(day_matches)

# ----- Prédire un match au choix -----
st.divider()
st.subheader("🎯 Prédire un autre match")

competition = st.selectbox("Compétition", list(COMPETITIONS.keys()))

try:
    with st.spinner("Chargement des données..."):
        matches = get_matches(COMPETITIONS[competition])
        model = build_model(mat
