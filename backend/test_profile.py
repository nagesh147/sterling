import sys
import os
sys.path.append("/home/nageshmadaram/Sterling/backend")
from app.engines.derivatives.profiles import get_profile, DEFAULT_PROFILES

print(get_profile("scalping/delta_gamma"))
