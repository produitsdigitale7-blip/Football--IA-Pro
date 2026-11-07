Pronostics foot gratuits : score probable, % de victoire, logos des clubs. Denis Paco Digital      f"{away} {r['lam_away']:.2f}"
        )
        st.write(f"**Forme de {home}** (5 derniers) : {recent_form(matches, home)}")
        st.write(f"**Forme de {away}** (5 derniers) : {recent_form(matches, away)}")

st.divider()
st.subheader("💬 Discute avec le bot")
st.caption("Écris un match, par exemple : PSG - Real Madrid ou Auxerre contre Monaco")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "Salut ! 👋 Écris-moi un match et je te donne ma prédiction. "
                "Exemple : `PSG - Real Madrid`"
            ),
        }
    ]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

prompt = st.chat_input("Écris un match, ex : PSG - Real Madrid")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Analyse en cours..."):
            reply = answer_chat(prompt, competition)
        st.markdown(reply)
    st.session_state.messages.append({"role": "assistant", "content": reply})

st.divider()
st.caption(
    "⚠️ Ces prédictions sont des probabilités statistiques, pas des certitudes. "
    "Elles ne tiennent pas compte des blessures ni des suspensions. "
    "Ne mise jamais d'argent que tu ne peux pas te permettre de perdre."
)# Football--IA-Pro
