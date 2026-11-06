import math

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
        for t in (h, a):
            teams.setdefault(t, {"gf": 0, "ga": 0, "n": 0})
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
    for t, s in teams.items():
        strengths[t] = {
            "attack": (s["gf"] / s["n"]) / avg_team,
            "defense": (s["ga"] / s["n"]) / avg_team,
        }
    return {"strengths": strengths, "avg_home": avg_home, "avg_away": avg_away}


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
st.caption(
    "⚠️ Ces prédictions sont des probabilités statistiques, pas des certitudes. "
    "Elles ne tiennent pas compte des blessures ni des suspensions. "
    "Ne mise jamais d'argent que tu ne peux pas te permettre de perdre."
  )
