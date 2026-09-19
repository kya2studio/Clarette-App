"""Keep the signed app bundle immutable while Python imports bundled modules."""
import os,sys
sys.dont_write_bytecode=True
os.environ['PYTHONDONTWRITEBYTECODE']='1'
