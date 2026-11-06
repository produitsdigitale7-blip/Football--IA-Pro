import random
import re
import unicodedata

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
