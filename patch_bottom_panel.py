import sys

filepath = "frontend/src/components/BottomPanel.tsx"
with open(filepath, "r") as f:
    content = f.read()

content = content.replace(
    "import { RiskConfigPanel } from './RiskConfigPanel';",
    "import { RiskConfigPanel, DailyLossPanel } from './RiskConfigPanel';"
)

content = content.replace(
    "<RiskConfigPanel />",
    "<DailyLossPanel />\n            <RiskConfigPanel />"
)

with open(filepath, "w") as f:
    f.write(content)
print("Patched BottomPanel.tsx")
