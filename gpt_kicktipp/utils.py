def get_user_from_keepassxc() -> str | None:
    try:
        from keepassxc_client import keepassxc
        creds = keepassxc.get_credentials("https://www.kicktipp.de/info/profil/login")[0]
        return creds["login"]
    except:
        return None

def get_password_from_keepassxc() -> tuple[str, str] | None:
    try:
        from keepassxc_client import keepassxc
        return keepassxc.get_first_password("https://www.kicktipp.de/info/profil/login")
    except:
        return None


def get_openai_api_key_from_keepassxc() -> str | None:
    try:
        from keepassxc_client import keepassxc
        return keepassxc.get_first_password("local-access://tng-ai-token.offline")
    except:
        return None
