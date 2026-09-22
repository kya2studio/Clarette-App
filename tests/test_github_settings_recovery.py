import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import preferences

class GithubSettingsRecoveryTests(unittest.TestCase):
 """github_login/github_avatar_type sit outside preferences.defaults()'s
 whitelist (same as the existing *_connected provider flags), so
 recover_settings() needs an explicit branch for them or a session reload
 silently drops the signed-in state -- which is exactly what "persist
 across restarts until sign out" requires it not to do."""
 def test_survives_session_recovery(self):
  result,repaired=preferences.recover_settings({'github_login':'octocat','github_avatar_type':'image/png'})
  self.assertEqual(result['github_login'],'octocat')
  self.assertEqual(result['github_avatar_type'],'image/png')
  self.assertFalse(repaired)
 def test_missing_is_fine(self):
  result,repaired=preferences.recover_settings({})
  self.assertNotIn('github_login',result)
  self.assertFalse(repaired)
 def test_invalid_type_is_dropped(self):
  result,repaired=preferences.recover_settings({'github_login':123})
  self.assertNotIn('github_login',result)
  self.assertTrue(repaired)

if __name__=='__main__':
 unittest.main()
