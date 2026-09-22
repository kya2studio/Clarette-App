import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import preferences

class IdentitySettingsRecoveryTests(unittest.TestCase):
 """identity_provider/identity_login/identity_avatar_type sit outside
 preferences.defaults()'s whitelist (same as the existing *_connected
 provider flags), so recover_settings() needs an explicit branch for them
 or a session reload silently drops the signed-in state -- which is
 exactly what "persist across restarts until sign out" requires it not to
 do, for whichever provider (GitHub or Google) the user signed in with."""
 def test_survives_session_recovery(self):
  result,repaired=preferences.recover_settings({'identity_provider':'google','identity_login':'a@example.com','identity_avatar_type':'image/jpeg'})
  self.assertEqual(result['identity_provider'],'google')
  self.assertEqual(result['identity_login'],'a@example.com')
  self.assertEqual(result['identity_avatar_type'],'image/jpeg')
  self.assertFalse(repaired)
 def test_missing_is_fine(self):
  result,repaired=preferences.recover_settings({})
  self.assertNotIn('identity_provider',result)
  self.assertFalse(repaired)
 def test_unknown_provider_is_dropped(self):
  result,repaired=preferences.recover_settings({'identity_provider':'facebook'})
  self.assertNotIn('identity_provider',result)
  self.assertTrue(repaired)
 def test_invalid_login_type_is_dropped(self):
  result,repaired=preferences.recover_settings({'identity_login':123})
  self.assertNotIn('identity_login',result)
  self.assertTrue(repaired)

if __name__=='__main__':
 unittest.main()
