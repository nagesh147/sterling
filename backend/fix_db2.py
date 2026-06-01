import sys
sys.path.append("/home/nageshmadaram/Sterling/backend")
from app.services.db import set_config, init

init()
set_config("derivatives_profiles", "")
print("Wiped derivatives_profiles!")
