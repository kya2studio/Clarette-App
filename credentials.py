"""macOS Keychain storage. Secrets never enter session JSON or command arguments."""
import sys
SERVICE='com.clarette.ai'
def api():
    if sys.platform!='darwin':raise ValueError('Secure API storage requires macOS Keychain')
    import Security
    return Security

def query(provider):
    if provider not in ('openai','gemini','seedream','github','google'):raise ValueError('Unknown provider')
    s=api();return {s.kSecClass:s.kSecClassGenericPassword,s.kSecAttrService:SERVICE,s.kSecAttrAccount:provider}

def set_key(provider,value):
    if not isinstance(value,str) or not 12<=len(value.strip())<=1024 or any(c.isspace() for c in value.strip()):raise ValueError('Enter a valid API key')
    s=api();q=query(provider);data=value.strip().encode()
    status=s.SecItemUpdate(q,{s.kSecValueData:data})
    if status==s.errSecItemNotFound:status,_=s.SecItemAdd({**q,s.kSecValueData:data},None)
    if status!=0:raise ValueError('Keychain could not save the key. Check macOS Keychain access.')

def get_key(provider):
    s=api();q=query(provider);q.update({s.kSecReturnData:True,s.kSecMatchLimit:s.kSecMatchLimitOne})
    status,data=s.SecItemCopyMatching(q,None)
    if status!=0:raise ValueError('Add this provider’s API key in Settings first')
    return bytes(data).decode()

def delete_key(provider):
    s=api();status=s.SecItemDelete(query(provider))
    if status not in (0,s.errSecItemNotFound):raise ValueError('Keychain could not remove the key')


def matches_key(provider,value):
    # Compare locally; never send the stored secret or its fingerprint to the UI.
    import hmac
    if provider not in ('openai','gemini','seedream'):raise ValueError('Unknown provider')
    if not isinstance(value,str) or not 12<=len(value.strip())<=1024:return False
    try:return hmac.compare_digest(value.strip().encode(),get_key(provider).encode())
    except ValueError:return False
