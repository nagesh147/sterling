import re

files = [
    "/home/nageshmadaram/Sterling/backend/app/engines/scalping/price_action.py",
    "/home/nageshmadaram/Sterling/backend/app/engines/scalping/smc.py",
    "/home/nageshmadaram/Sterling/backend/app/engines/scalping/ma_crossover.py"
]

for file_path in files:
    with open(file_path, "r") as f:
        content = f.read()
    
    # Remove tp_source: str = "" from its current place
    content = content.replace("    tp_source: str = \"\"\n", "")
    
    # Add it after timestamp_ms: int
    content = content.replace("    timestamp_ms: int\n", "    timestamp_ms: int\n    tp_source: str = \"\"\n")
    
    with open(file_path, "w") as f:
        f.write(content)

