import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader

st.set_page_config(page_title="Test Auth — INDUSFLOW", page_icon="🔐")

# ----------------------------------------------------------------------------
# Chargement de la config
# ----------------------------------------------------------------------------

with open("config.yaml") as file:
    config = yaml.load(file, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    config["credentials"],
    config["cookie"]["name"],
    config["cookie"]["key"],
    config["cookie"]["expiry_days"],
)

# ----------------------------------------------------------------------------
# Widget de login
# ----------------------------------------------------------------------------

authenticator.login(location="main")

# ----------------------------------------------------------------------------
# Résultat de l'authentification
# ----------------------------------------------------------------------------

if st.session_state.get("authentication_status"):
    authenticator.logout(location="sidebar")

    username = st.session_state["username"]
    name = st.session_state["name"]
    role = config["credentials"]["usernames"][username].get("role", "inconnu")

    st.success(f"Connecté(e) en tant que **{name}**")
    st.write(f"Nom d'utilisateur : `{username}`")
    st.write(f"Rôle détecté : **{role}**")

    st.divider()
    st.info(
        "Étape suivante : ce `role` sera utilisé dans `app.py` pour décider "
        "quels onglets afficher à cette personne."
    )

elif st.session_state.get("authentication_status") is False:
    st.error("Nom d'utilisateur ou mot de passe incorrect.")

elif st.session_state.get("authentication_status") is None:
    st.warning("Merci de te connecter pour continuer.")