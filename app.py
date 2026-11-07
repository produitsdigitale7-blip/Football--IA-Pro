import html
import math
from datetime import datetime, timedelta, timezone

import requests
import streamlit as st

API_URL = "https://api.football-data.org/v4"

CODES = ["FL1", "PL", "ELC", "PD", "SA", "BL1", "DED", "PPL", "BSA", "CL"]

MAX_GOALS = 10


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
    """Récupère les matchs d'un jour donné dans tous les championnats."""
    headers = {"X-Auth-Token": st.secrets["FOOTBALL_API_KEY"]}
    d0 = datetime.fromisoformat(day_iso).date()
    r = requests.get(
        f"{API_URL}/matches",
        headers=headers,
        params={
            "dateFrom": day_iso,
            "dateTo": (d0 + timedelta(days=1)).isoformat(),
            "competitions": ",".join(CODES),
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
        teams.setdefault(h, {"gf": 0, "ga": 0, "n": 0})
        teams.setdefault(a, {"gf": 0, "ga": 0, "n": 0})
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


# ---------- LISTE DES MATCHS ----------
def render_day_matches(day_matches):
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

                mid = m["id"]
                opened = mid in st.session_state.opened
                label = "🔼 Masquer la prédiction" if opened else "🔮 Voir la prédiction"
                if st.button(label, key=f"btn_{mid}", use_container_width=True):
                    if opened:
                        st.session_state.opened.discard(mid)
                    else:
                        st.session_state.opened.add(mid)
                    st.rerun()

                if opened:
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


# ---------- INTERFACE ----------
st.set_page_config(page_title="Prédictions Foot", page_icon="⚽", layout="centered")

if "opened" not in st.session_state:
    st.session_state.opened = set()

st.title("⚽ Prédictions de matchs")
st.caption("Denis Paco Digital — analyse statistique des matchs de football")

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
    if not day_matches:
        st.info("Aucun match ce jour-là dans ces championnats. Essaie un autre jour.")
    else:
        names = sorted({m["competition"]["name"] for m in day_matches})
        pick = st.selectbox("Championnat", ["Tous les championnats", *names])
        if pick != "Tous les championnats":
            day_matches = [m for m in day_matches if m["competition"]["name"] == pick]
        render_day_matches(day_matches)

st.divider()
st.caption(
    "⚠️ Ces prédictions sont des probabilités statistiques, pas des certitudes. "
    "Elles ne tiennent pas compte des blessures ni des suspensions. "
    "Ne mise jamais d'argent que tu ne peux pas te permettre de perdre."
        )
