"""Authentication component using streamlit-authenticator."""

import streamlit as st
import streamlit_authenticator as stauth
import yaml
from pathlib import Path


def check_auth() -> bool:
    """Check authentication status, show login if needed.

    Returns:
        bool: True if user is authenticated, False otherwise
    """
    config_path = Path(__file__).parent.parent / "config.yaml"

    # Check if config exists
    if not config_path.exists():
        st.error("Authentication configuration not found!")
        st.info(
            "Please create `config.yaml` from `config.yaml.example` "
            "and configure your credentials."
        )
        st.code(
            """
# Generate password hash:
python -c "import streamlit_authenticator as stauth; print(stauth.Hasher(['your_password']).generate())"

# Generate cookie key:
python -c "import secrets; print(secrets.token_hex(32))"
            """,
            language="bash",
        )
        return False

    # Initialize authenticator if not already done
    if "authenticator" not in st.session_state:
        try:
            with open(config_path) as f:
                config = yaml.safe_load(f)

            st.session_state.authenticator = stauth.Authenticate(
                config["credentials"],
                config["cookie"]["name"],
                config["cookie"]["key"],
                config["cookie"]["expiry_days"],
            )
        except Exception as e:
            st.error(f"Failed to load authentication config: {e}")
            return False

    # Show login form
    st.session_state.authenticator.login()

    # Check authentication status
    if st.session_state.get("authentication_status"):
        st.session_state.username = st.session_state.get("name", "User")
        return True
    elif st.session_state.get("authentication_status") is False:
        st.error("Invalid username or password")
        return False
    else:
        # None = not yet attempted
        st.warning("Please enter your credentials")
        return False


def logout() -> None:
    """Log out the current user."""
    if "authenticator" in st.session_state:
        st.session_state.authenticator.logout()
